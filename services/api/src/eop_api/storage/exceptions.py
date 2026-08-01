class StorageObjectNotFoundError(Exception):
    """Raised when a download/delete targets a key that does not exist in the backend."""

    def __init__(self, key: str) -> None:
        super().__init__(f"Object not found in storage: {key}")
        self.key = key
