"""Pruebas de priorización de temperatura real y respaldo identificado."""
import pathlib
import unittest

BASE=pathlib.Path(__file__).resolve().parents[1]

class CurrentTemperatureUITests(unittest.TestCase):
    def test_prioritizes_real_estanzuela(self):
        html=(BASE/"index.html").read_text(encoding="utf-8")
        current=html.split("async function loadCurrent(){",1)[1].split("function renderSkill(score){",1)[0]
        self.assertIn("getJson('./data/current_station.json')",current)
        self.assertIn("data?.station_id!==584",current)
        self.assertIn("data?.observation!==true",current)
        self.assertIn("age > 120",current)
        self.assertIn("kind.textContent='Medición'",current)
        self.assertIn("return; // La medición real tiene prioridad",current)
        self.assertLess(current.index("getJson('./data/current_station.json')"),
                        current.index("fetch(CURRENT_ESTIMATE_URL"))

    def test_fallback_does_not_masquerade_as_measurement(self):
        html=(BASE/"index.html").read_text(encoding="utf-8")
        current=html.split("async function loadCurrent(){",1)[1].split("function renderSkill(score){",1)[0]
        self.assertIn("kind.textContent='Estimación'",current)
        self.assertIn("No es una medición",current)
        self.assertIn("INIA sin lectura reciente.",current)
        self.assertIn("age > 90",current)
        self.assertIn("kind.textContent='Sin dato'",current)
        self.assertIn("value.textContent='— °C'",current)

    def test_station_source_is_transparent(self):
        html=(BASE/"index.html").read_text(encoding="utf-8")
        card=html.split('<section class="now"',1)[1].split("</section>",1)[0]
        self.assertIn('id="now-source"',card)
        self.assertIn('INUMET / INIA La Estanzuela',card)
        self.assertIn('No es Rosario',card)

if __name__=="__main__": unittest.main()
