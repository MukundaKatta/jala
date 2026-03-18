"""Tests for Jala."""
from src.core import Jala
def test_init(): assert Jala().get_stats()["ops"] == 0
def test_op(): c = Jala(); c.process(x=1); assert c.get_stats()["ops"] == 1
def test_multi(): c = Jala(); [c.process() for _ in range(5)]; assert c.get_stats()["ops"] == 5
def test_reset(): c = Jala(); c.process(); c.reset(); assert c.get_stats()["ops"] == 0
def test_service_name(): c = Jala(); r = c.process(); assert r["service"] == "jala"
