"""Pruebas: observación real con fuente precisa y respaldo identificado."""
import pathlib
import unittest

BASE=pathlib.Path(__file__).resolve().parents[1]

class CurrentTemperatureUITests(unittest.TestCase):
    def setUp(self):
        html=(BASE/"index.html").read_text(encoding="utf-8")
        self.current=html.split("async function loadCurrent(){",1)[1].split("function renderSkill(score){",1)[0]
        self.card=html.split('<section class="now"',1)[1].split("</section>",1)[0]

    def test_prioritizes_verified_station_observation(self):
        current=self.current
        self.assertIn("getJson('./data/current_station.json')",current)
        self.assertIn("data?.station_id===584",current)
        self.assertIn("data?.station_id===594",current)
        self.assertIn("INUMET / Colonia G3",current)
        self.assertIn("data?.observation!==true",current)
        self.assertIn("age > 120",current)
        self.assertIn("kind.textContent='Medición'",current)
        self.assertIn("return; // La medición real tiene prioridad",current)
        self.assertLess(current.index("getJson('./data/current_station.json')"),
                        current.index("fetch(CURRENT_ESTIMATE_URL"))

    def test_fallback_does_not_masquerade_as_measurement(self):
        current=self.current
        self.assertIn("kind.textContent='Estimación'",current)
        self.assertIn("No es una medición",current)
        self.assertIn("Estaciones oficiales sin lectura reciente.",current)
        self.assertIn("age > 90",current)
        self.assertIn("kind.textContent='Sin dato'",current)
        self.assertIn("value.textContent='— °C'",current)

    def test_station_source_is_transparent(self):
        self.assertIn('id="now-source"',self.card)
        self.assertIn('id="now-link"',self.card)
        self.assertIn('Estaciones cercanas a Rosario',self.card)
        self.assertIn("station.name",self.current)
        self.assertIn("(no Rosario)",self.current)

if __name__=="__main__":unittest.main()
