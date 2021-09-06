"""Stub for settings object that can be configured manually or read variables from environment"""
from pydantic import BaseSettings


class Settings(BaseSettings):
    name: str

    class Config:
        env_prefix = "movici_"
