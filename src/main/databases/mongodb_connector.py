"""Connector for the SoftCart MongoDB product catalog."""

from __future__ import annotations

from typing import Any, Iterable

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from src.main.utility.config_loader import get_config
from src.main.utility.exceptions import DatabaseConnectionError, ETLError
from src.main.utility.logger import get_logger

logger = get_logger(__name__)


class MongoDBConnector:
    """Wrapper over pymongo for the product catalog collection."""

    def __init__(self) -> None:
        config = get_config()
        self._host = config.get("mongodb", "host")
        self._port = config.get_int("mongodb", "port")
        self._user = config.get("mongodb", "user")
        self._password = config.get("mongodb", "password")
        self._database = config.get("mongodb", "database")
        self._collection = config.get("mongodb", "collection")
        self._client: MongoClient | None = None

    @property
    def client(self) -> MongoClient:
        """Lazily created, authenticated Mongo client."""
        if self._client is None:
            try:
                self._client = MongoClient(
                    host=self._host,
                    port=self._port,
                    username=self._user,
                    password=self._password,
                    serverSelectionTimeoutMS=10_000,
                )
                self._client.admin.command("ping")
                logger.info("Connected to mongodb")
            except PyMongoError as exc:
                raise DatabaseConnectionError(f"MongoDB connection failed: {exc}") from exc
        return self._client

    @property
    def products(self) -> Collection:
        """The product catalog collection."""
        return self.client[self._database][self._collection]

    def replace_products(self, documents: Iterable[dict[str, Any]]) -> int:
        """Drop and reload the catalog; returns the inserted document count."""
        docs = list(documents)
        try:
            self.products.drop()
            if docs:
                self.products.insert_many(docs)
            self.products.create_index("product_id", unique=True)
            self.products.create_index("category.name")
            logger.info("mongodb: loaded {} product documents", len(docs))
            return len(docs)
        except PyMongoError as exc:
            raise ETLError(f"MongoDB product load failed: {exc}") from exc

    def fetch_products(self) -> list[dict[str, Any]]:
        """Return all product documents without Mongo's internal _id."""
        try:
            docs = list(self.products.find({}, {"_id": 0}))
            logger.debug("mongodb: fetched {} product documents", len(docs))
            return docs
        except PyMongoError as exc:
            raise ETLError(f"MongoDB product fetch failed: {exc}") from exc

    def close(self) -> None:
        """Close the client connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
