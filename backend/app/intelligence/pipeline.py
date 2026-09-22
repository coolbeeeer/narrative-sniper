import asyncio
import uuid
from datetime import datetime
from typing import Optional
import numpy as np
from sentence_transformers import SentenceTransformer
import hdbscan
from sklearn.feature_extraction.text import TfidfVectorizer
import structlog

from app.core.config import settings
from app.models.narrative import Narrative, NarrativeCluster, SourceRef
from app.models.token import Token


logger = structlog.get_logger()


class IntelligencePipeline:
    def __init__(self):
        self.embedder: Optional[SentenceTransformer] = None
        self.clusterer: Optional[hdbscan.HDBSCAN] = None
        self.vectorizer: Optional[TfidfVectorizer] = None
        
        self.narratives: dict[str, Narrative] = {}
        self.clusters: dict[str, NarrativeCluster] = {}
        self.pending_items: list[dict] = []
        self.processing = False
        self.process_task: Optional[asyncio.Task] = None
        self.narrative_listeners: list = []  # async callbacks fired per new narrative

    def on_narrative(self, callback):
        """Register an async callback invoked with each new Narrative."""
        self.narrative_listeners.append(callback)

    async def initialize(self):
        logger.info("Initializing intelligence pipeline")
        
        # Load embedding model
        self.embedder = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info("Embedding model loaded", model=settings.EMBEDDING_MODEL)
        
        # Initialize clusterer
        self.clusterer = hdbscan.HDBSCAN(
            min_cluster_size=settings.CLUSTER_MIN_SIZE,
            min_samples=settings.CLUSTER_MIN_SAMPLES,
            metric="euclidean",
            cluster_selection_method="eom",
        )
        
        # Initialize vectorizer for keyword extraction
        self.vectorizer = TfidfVectorizer(
            max_features=100,
            stop_words="english",
            ngram_range=(1, 2),
        )
        
        logger.info("Intelligence pipeline initialized")

    async def shutdown(self):
        if self.process_task:
            self.process_task.cancel()
            try:
                await self.process_task
            except asyncio.CancelledError:
                pass

    async def process(self, item: dict):
        self.pending_items.append(item)
        if len(self.pending_items) >= settings.INGESTION_BATCH_SIZE and not self.processing:
            await self._process_batch()

    async def _process_batch(self):
        if self.processing or not self.pending_items:
            return

        self.processing = True
        items = self.pending_items[:settings.INGESTION_BATCH_SIZE]
        self.pending_items = self.pending_items[settings.INGESTION_BATCH_SIZE:]

        try:
            await self._run_intelligence_pipeline(items)
        finally:
            self.processing = False
            if self.pending_items:
                await self._process_batch()

    async def _run_intelligence_pipeline(self, items: list[dict]):
        # Extract texts for embedding
        texts = [item.get("text", "") for item in items if item.get("text")]
        if not texts:
            return

        # Generate embeddings
        embeddings = self.embedder.encode(texts, show_progress_bar=False)
        
        # Cluster embeddings
        cluster_labels = self.clusterer.fit_predict(embeddings)
        
        # Group items by cluster
        clusters: dict[int, list[tuple[dict, np.ndarray]]] = {}
        for item, embedding, label in zip(items, embeddings, cluster_labels):
            if label >= 0:
                clusters.setdefault(label, []).append((item, embedding))

        # Process each cluster
        for cluster_id, cluster_items in clusters.items():
            await self._process_cluster(cluster_id, cluster_items)

    async def _process_cluster(self, cluster_id: int, cluster_items: list[tuple[dict, np.ndarray]]):
        # Calculate cluster centroid
        embeddings = np.array([emb for _, emb in cluster_items])
        centroid = embeddings.mean(axis=0)
        
        # Extract texts
        texts = [item.get("text", "") for item, _ in cluster_items]
        sources = [self._extract_source_ref(item) for item, _ in cluster_items]
        
        # Extract top tokens from texts
        top_tokens = self._extract_tokens(texts)
        
        # Generate narrative label using LLM
        label, description, confidence = await self._label_cluster(texts, top_tokens)
        
        if confidence < settings.NARRATIVE_CONFIDENCE_THRESHOLD:
            return

        # Create or update narrative
        narrative_id = str(uuid.uuid4())
        narrative = Narrative(
            id=narrative_id,
            label=label,
            description=description,
            confidence=confidence,
            cluster_size=len(cluster_items),
            top_tokens=top_tokens[:10],
            sources=sources,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        self.narratives[narrative_id] = narrative
        
        # Store cluster info
        self.clusters[str(cluster_id)] = NarrativeCluster(
            id=str(cluster_id),
            narrative_id=narrative_id,
            centroid=centroid.tolist(),
            items=[item for item, _ in cluster_items],
        )
        
        logger.info("New narrative detected", label=label, confidence=confidence, size=len(cluster_items))

        for listener in self.narrative_listeners:
            try:
                await listener(narrative)
            except Exception as e:
                logger.warning("Narrative listener failed", error=str(e))

    def _extract_source_ref(self, item: dict) -> SourceRef:
        return SourceRef(
            platform=item.get("platform", "unknown"),
            handle=item.get("handle", "unknown"),
            url=item.get("url", ""),
            timestamp=item.get("timestamp", datetime.utcnow().isoformat()),
            engagement=item.get("engagement", 0),
        )

    def _extract_tokens(self, texts: list[str]) -> list[str]:
        # Simple token extraction - look for $SYMBOL or #SYMBOL patterns
        import re
        tokens = set()
        for text in texts:
            # Match $SYMBOL or #SYMBOL
            matches = re.findall(r'[\$#]([A-Z]{2,10})', text.upper())
            tokens.update(matches)
        return list(tokens)[:20]

    async def _label_cluster(self, texts: list[str], tokens: list[str]) -> tuple[str, str, float]:
        # Prefer NVIDIA NIM (free tier) for labeling; fall back to heuristic
        if settings.NVIDIA_API_KEY:
            try:
                return await self._label_cluster_llm(texts, tokens)
            except Exception as e:
                logger.warning("NVIDIA NIM labeling failed, using heuristic", error=str(e))

        return self._label_cluster_heuristic(texts, tokens)

    async def _label_cluster_llm(self, texts: list[str], tokens: list[str]) -> tuple[str, str, float]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            base_url=settings.NVIDIA_API_BASE,
            api_key=settings.NVIDIA_API_KEY,
        )

        sample = "\n".join(f"- {t[:280]}" for t in texts[:15])
        token_hint = f"Tokens mentioned: {', '.join(tokens[:8])}." if tokens else "No token symbols detected."

        prompt = (
            "You are a crypto market analyst. Below are social media posts that clustered together "
            "as one emerging narrative. Summarize the narrative in a short label.\n\n"
            f"{sample}\n\n{token_hint}\n\n"
            'Respond with ONLY valid JSON: {"label": "<=6 word narrative label>", '
            '"description": "<=25 word explanation>", "confidence": <0.0-1.0>}'
        )

        resp = await client.chat.completions.create(
            model=settings.NVIDIA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=200,
            response_format={"type": "json_object"},
        )

        import json
        data = json.loads(resp.choices[0].message.content or "{}")
        label = str(data.get("label", "Emerging Narrative"))[:80]
        description = str(data.get("description", ""))[:300]
        try:
            confidence = float(data.get("confidence", 0.6))
        except (TypeError, ValueError):
            confidence = 0.6
        confidence = max(0.0, min(1.0, confidence))

        logger.info("Narrative labeled via NVIDIA NIM", label=label, confidence=confidence)
        return label, description, confidence

    def _label_cluster_heuristic(self, texts: list[str], tokens: list[str]) -> tuple[str, str, float]:
        
        # Extract key phrases using TF-IDF
        try:
            tfidf = self.vectorizer.fit_transform([combined])
            feature_names = self.vectorizer.get_feature_names_out()
            scores = tfidf.toarray()[0]
            top_indices = scores.argsort()[-5:][::-1]
            key_phrases = [feature_names[i] for i in top_indices if scores[i] > 0]
        except Exception:
            key_phrases = []

        # Generate label
        if tokens:
            label = f"{tokens[0]} Narrative"
        elif key_phrases:
            label = key_phrases[0].title() + " Narrative"
        else:
            label = "Emerging Narrative"

        description = f"Detected from {len(texts)} sources discussing {', '.join(tokens[:5]) if tokens else 'crypto topics'}"
        confidence = min(0.9, 0.5 + len(texts) * 0.05)

        return label, description, confidence

    def get_narratives(
        self,
        page: int = 1,
        page_size: int = 50,
        min_confidence: float = 0.0,
    ) -> list[Narrative]:
        filtered = [
            n for n in self.narratives.values()
            if n.confidence >= min_confidence
        ]
        filtered.sort(key=lambda x: x.updated_at, reverse=True)
        start = (page - 1) * page_size
        end = start + page_size
        return filtered[start:end]

    def get_narrative(self, narrative_id: str) -> Optional[Narrative]:
        return self.narratives.get(narrative_id)

    def get_active_narratives_count(self) -> int:
        return len([n for n in self.narratives.values() if n.confidence >= settings.NARRATIVE_CONFIDENCE_THRESHOLD])