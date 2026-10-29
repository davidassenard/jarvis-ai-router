import unittest
from router import Router, ProviderError

class RouterTests(unittest.TestCase):
    def test_primary_success(self):
        r = Router({"groq": lambda _: "ok", "gemini": lambda _: "later"}, ["groq", "gemini"])
        out = r.complete([{"role": "user", "content": "bonjour"}])
        self.assertEqual((out.provider, out.attempts, out.text), ("groq", ("groq",), "ok"))

    def test_rate_limit_falls_back(self):
        def failed(_): raise ProviderError("groq", True, 429)
        r = Router({"groq": failed, "gemini": lambda _: "réponse"}, ["groq", "gemini"])
        out = r.complete([])
        self.assertEqual((out.provider, out.attempts), ("gemini", ("groq", "gemini")))

    def test_non_retryable_does_not_hide_bad_request(self):
        def failed(_): raise ProviderError("groq", False, 400)
        with self.assertRaises(ProviderError): Router({"groq": failed, "gemini": lambda _: "x"}, ["groq", "gemini"]).complete([])

    def test_web_context_is_added_only_for_current_questions(self):
        seen = []
        def provider(messages):
            seen.extend(messages)
            return "réponse"
        r = Router({"gemini": provider}, ["gemini"], lambda q: [{"title":"Météo", "url":"https://example.test/meteo", "content":"prévisions"}])
        r.complete([{"role":"user", "content":"Quel temps fera-t-il demain ?"}])
        self.assertEqual(seen[0]["role"], "system")
        self.assertIn("https://example.test/meteo", seen[0]["content"])

    def test_web_search_failure_keeps_normal_conversation(self):
        seen = []
        r = Router({"gemini": lambda m: seen.extend(m) or "ok"}, ["gemini"], lambda _: [])
        r.complete([{"role":"user", "content":"Bonjour"}])
        self.assertEqual(seen, [{"role":"user", "content":"Bonjour"}])

if __name__ == "__main__": unittest.main()
