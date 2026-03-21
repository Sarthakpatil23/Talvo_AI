from django.test import SimpleTestCase

from .rag_retriever import InterviewRAGRetriever


class InterviewRAGRetrieverTests(SimpleTestCase):
	def test_retrieval_returns_top_k(self):
		retriever = InterviewRAGRetriever()
		results = retriever.retrieve(
			company='Amazon',
			role='Software Engineer',
			difficulty='Medium',
			interview_type='Technical',
			user_transcript='I reduced latency and fixed retry storms in a service under load.',
			history=[],
			top_k=3,
		)

		self.assertGreaterEqual(len(results), 1)
		self.assertLessEqual(len(results), 3)

	def test_top_result_is_context_aligned_for_google_sde(self):
		retriever = InterviewRAGRetriever()
		results = retriever.retrieve(
			company='Google',
			role='Software Engineer',
			difficulty='Hard',
			interview_type='System Design',
			user_transcript='I designed a distributed ingestion pipeline with strict reliability requirements.',
			history=[],
			top_k=3,
		)

		self.assertGreaterEqual(len(results), 1)
		top = results[0]
		self.assertIn('google', str(top.get('company', '')))
		self.assertIn('software', str(top.get('role', '')))
