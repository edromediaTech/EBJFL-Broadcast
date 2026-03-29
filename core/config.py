"""Configuration centralisée pour EBJFL-Broadcast."""

from dataclasses import dataclass, field


@dataclass
class OBSConfig:
    host: str = "localhost"
    port: int = 4455
    password: str = "liveebjfl"


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000


@dataclass
class AppConfig:
    obs: OBSConfig = field(default_factory=OBSConfig)
    server: ServerConfig = field(default_factory=ServerConfig)


config = AppConfig()
