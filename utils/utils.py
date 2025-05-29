import sqlite3
import queue
import threading

class SQLiteConnectionPool:
    """Manages a pool of SQLite database connections."""

    def __init__(self, db_path: str, max_connections: int = 10):
        """Initializes the SQLiteConnectionPool.

        Args:
            db_path (str): Path to the SQLite database file.
            max_connections (int): Maximum number of connections in the pool.
        """
        self.db_path = db_path
        self.max_connections = max_connections
        self.connections = queue.Queue(maxsize=max_connections)
        self.connection_count = 0
        self.lock = threading.Lock()

        for _ in range(min(3, max_connections)):
            self._create_connection()

    def _create_connection(self) -> bool:
        """Creates a new SQLite connection and adds it to the pool.

        Returns:
            bool: True if a connection was created, False otherwise.
        """
        if self.connection_count >= self.max_connections:
            return False

        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = 10000")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA mmap_size = 30000000")

        with self.lock:
            self.connection_count += 1

        self.connections.put(conn)
        return True

    def get_connection(self, timeout: int = 5) -> sqlite3.Connection:
        """Retrieves a connection from the pool.

        Args:
            timeout (int): Timeout in seconds to wait for a connection.

        Returns:
            sqlite3.Connection: A SQLite connection object.
        """
        try:
            return self.connections.get(timeout=timeout)
        except queue.Empty:
            with self.lock:
                if self.connection_count < self.max_connections:
                    conn = sqlite3.connect(
                        self.db_path, check_same_thread=False
                    )
                    conn.execute("PRAGMA journal_mode = WAL")
                    conn.execute("PRAGMA synchronous = NORMAL")
                    conn.execute("PRAGMA cache_size = 10000")
                    conn.execute("PRAGMA temp_store = MEMORY")
                    conn.execute("PRAGMA mmap_size = 30000000")
                    self.connection_count += 1
                    return conn

            return self.connections.get(timeout=timeout)

    def return_connection(self, conn: sqlite3.Connection) -> None:
        """Returns a connection to the pool.

        Args:
            conn (sqlite3.Connection): The SQLite connection object to return.
        """
        if conn:
            self.connections.put(conn)

    def close_all(self) -> None:
        """Closes all connections in the pool."""
        while not self.connections.empty():
            try:
                conn = self.connections.get_nowait()
                conn.close()
            except queue.Empty:
                break

        with self.lock:
            self.connection_count = 0