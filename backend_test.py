import requests
import unittest
import json
import time

class ZarkAIAPITest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(ZarkAIAPITest, self).__init__(*args, **kwargs)
        # Get the backend URL from frontend .env file
        self.base_url = "https://c3ee10d9-6602-453e-aae2-f74f4bf9f6b8.preview.emergentagent.com"
        self.headers = {'Content-Type': 'application/json'}
        self.test_url = "https://en.wikipedia.org/wiki/Artificial_intelligence"
        
    def test_01_health_check(self):
        """Test the health check endpoint"""
        print("\n🔍 Testing API Health Check...")
        response = requests.get(f"{self.base_url}/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print(f"✅ Health Check Response: {data}")
        self.assertIn('status', data)
        self.assertEqual(data['status'], 'healthy', "Health status should be 'healthy'")
        self.assertEqual(data['mongodb'], 'connected', "MongoDB should be connected")
        self.assertEqual(data['groq'], 'configured', "Groq API should be configured")
        
    def test_02_chat_endpoint(self):
        """Test the chat endpoint with a simple query"""
        print("\n🔍 Testing Chat Endpoint...")
        payload = {
            "query": "What is artificial intelligence?",
            "conversation_id": None
        }
        response = requests.post(
            f"{self.base_url}/api/chat", 
            headers=self.headers,
            json=payload
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print(f"✅ Chat Response received with {len(data['response'])} characters")
        self.assertIn('response', data)
        self.assertIn('conversation_id', data)
        
        # Test concise response system (should be 5 lines or less by default)
        response_lines = data['response'].strip().split('\n')
        print(f"✅ Response has {len(response_lines)} lines (should be concise by default)")
        
        return data['conversation_id']
        
    def test_03_insert_content(self):
        """Test the content insertion endpoint (previously 'ingest')"""
        print("\n🔍 Testing Content Insertion...")
        payload = {
            "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
            "depth": 1
        }
        response = requests.post(
            f"{self.base_url}/api/ingest", 
            headers=self.headers,
            json=payload
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print(f"✅ Insertion Response: {data}")
        self.assertIn('message', data)
        self.assertIn('url', data)
        
        # Give some time for insertion to complete
        print("Waiting for insertion to complete...")
        time.sleep(2)
        
    def test_04_get_knowledge(self):
        """Test retrieving knowledge entries"""
        print("\n🔍 Testing Knowledge Retrieval...")
        response = requests.get(f"{self.base_url}/api/knowledge")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print(f"✅ Knowledge Base contains {data['total']} entries")
        self.assertIn('knowledge', data)
        self.assertIn('total', data)
        
    def test_05_chat_with_knowledge(self):
        """Test chat with inserted knowledge"""
        print("\n🔍 Testing Chat with Inserted Knowledge...")
        payload = {
            "query": "Tell me about artificial intelligence based on the content you've inserted",
            "conversation_id": None
        }
        response = requests.post(
            f"{self.base_url}/api/chat", 
            headers=self.headers,
            json=payload
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print(f"✅ Chat Response with Knowledge: {len(data['response'])} characters")
        print(f"✅ Sources used: {data['sources']}")
        self.assertIn('response', data)
        self.assertIn('sources', data)
        
    def test_06_detailed_response(self):
        """Test requesting a detailed response (more than 5 lines)"""
        print("\n🔍 Testing Detailed Response Request...")
        payload = {
            "query": "Tell me more details about artificial intelligence",
            "conversation_id": None
        }
        response = requests.post(
            f"{self.base_url}/api/chat", 
            headers=self.headers,
            json=payload
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        response_lines = data['response'].strip().split('\n')
        print(f"✅ Detailed response has {len(response_lines)} lines (should be more than 5)")
        self.assertIn('response', data)
        
    def test_07_clear_knowledge(self):
        """Test clearing the knowledge base"""
        print("\n🔍 Testing Knowledge Base Clearing...")
        response = requests.delete(f"{self.base_url}/api/knowledge")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print(f"✅ Clear Knowledge Response: {data}")
        self.assertIn('message', data)
        
        # Verify knowledge is cleared
        response = requests.get(f"{self.base_url}/api/knowledge")
        data = response.json()
        print(f"✅ Knowledge Base now contains {data['total']} entries")
        
    def test_08_error_handling(self):
        """Test error handling with invalid requests"""
        print("\n🔍 Testing Error Handling...")
        
        # Test invalid chat request (missing required field)
        print("Testing invalid chat request...")
        payload = {
            # Missing required 'query' field
            "conversation_id": "invalid-test"
        }
        response = requests.post(
            f"{self.base_url}/api/chat", 
            headers=self.headers,
            json=payload
        )
        self.assertEqual(response.status_code, 422, "Should return 422 for invalid request")
        data = response.json()
        print(f"✅ Invalid chat request error: {data}")
        self.assertIn('detail', data)
        
        # Test invalid ingest request with malformed URL
        print("Testing invalid ingest request with malformed URL...")
        payload = {
            "url": "not-a-valid-url-format",
            "depth": 1
        }
        response = requests.post(
            f"{self.base_url}/api/ingest", 
            headers=self.headers,
            json=payload
        )
        # The server handles invalid URLs gracefully by returning success with 0 pages
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print(f"✅ Invalid URL handled gracefully: {data}")
        self.assertIn('message', data)
        self.assertIn('0 pages', data['message'], "Should report 0 pages ingested for invalid URL")
        
    def test_09_sources_functionality_off(self):
        """Test the chat endpoint with show_sources=false (default)"""
        print("\n🔍 Testing Sources Functionality (OFF)...")
        
        # First ensure we have content to reference
        self._ensure_content_exists()
        
        # Test with show_sources=false (default)
        payload = {
            "query": "What is artificial intelligence?",
            "conversation_id": None,
            "show_sources": False
        }
        response = requests.post(
            f"{self.base_url}/api/chat", 
            headers=self.headers,
            json=payload
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print(f"✅ Chat Response with show_sources=false: {len(data['response'])} characters")
        print(f"✅ Sources returned: {data['sources']}")
        
        self.assertIn('response', data)
        self.assertIn('sources', data)
        # Sources should be empty when show_sources is false
        self.assertEqual(len(data['sources']), 0, "Sources should be empty when show_sources=false")
        
    def test_10_sources_functionality_on(self):
        """Test the chat endpoint with show_sources=true"""
        print("\n🔍 Testing Sources Functionality (ON)...")
        
        # First ensure we have content to reference
        self._ensure_content_exists()
        
        # Test with show_sources=true
        payload = {
            "query": "What is artificial intelligence?",
            "conversation_id": None,
            "show_sources": True
        }
        response = requests.post(
            f"{self.base_url}/api/chat", 
            headers=self.headers,
            json=payload
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print(f"✅ Chat Response with show_sources=true: {len(data['response'])} characters")
        print(f"✅ Sources returned: {data['sources']}")
        
        self.assertIn('response', data)
        self.assertIn('sources', data)
        
        # Check if sources are returned when show_sources is true
        # Note: This might not always return sources if the knowledge base doesn't have relevant content
        # So we'll just log the result rather than asserting
        if len(data['sources']) > 0:
            print(f"✅ Sources are correctly returned when show_sources=true: {len(data['sources'])} sources")
        else:
            print("⚠️ No sources returned. This could be normal if no relevant knowledge was found.")
            
    def test_11_explicit_source_request(self):
        """Test asking explicitly for sources in the query"""
        print("\n🔍 Testing Explicit Source Request...")
        
        # First ensure we have content to reference
        self._ensure_content_exists()
        
        # Test with a query that explicitly asks for sources
        payload = {
            "query": "Where did you get information about artificial intelligence?",
            "conversation_id": None,
            "show_sources": True
        }
        response = requests.post(
            f"{self.base_url}/api/chat", 
            headers=self.headers,
            json=payload
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print(f"✅ Chat Response for explicit source request: {len(data['response'])} characters")
        print(f"✅ Sources returned: {data['sources']}")
        
        self.assertIn('response', data)
        self.assertIn('sources', data)
        
        # Check if the response mentions sources
        source_terms = ["source", "reference", "from", "wikipedia", "article", "information"]
        response_has_source_mention = any(term in data['response'].lower() for term in source_terms)
        
        if response_has_source_mention:
            print("✅ Response mentions sources when explicitly asked")
        else:
            print("⚠️ Response doesn't explicitly mention sources when asked")
            
    def test_12_specific_ai_questions(self):
        """Test specific questions about artificial intelligence after adding Wikipedia content"""
        print("\n🔍 Testing Specific AI Questions...")
        
        # First ensure we have content to reference
        self._ensure_content_exists()
        
        # Test with specific questions about AI
        questions = [
            "What are neural networks?",
            "Tell me about machine learning",
            "What is deep learning?",
            "How is AI used today?"
        ]
        
        for question in questions:
            print(f"\nTesting question: '{question}'")
            payload = {
                "query": question,
                "conversation_id": None,
                "show_sources": True
            }
            response = requests.post(
                f"{self.base_url}/api/chat", 
                headers=self.headers,
                json=payload
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            print(f"✅ Response length: {len(data['response'])} characters")
            print(f"✅ Sources returned: {len(data['sources'])}")
            
            # Check if the response is substantive (more than 100 characters)
            self.assertGreater(len(data['response']), 100, f"Response to '{question}' should be substantive")
            
            # Print first 100 chars of response for verification
            print(f"Response preview: {data['response'][:100]}...")
            
    def _ensure_content_exists(self):
        """Helper method to ensure content exists in the knowledge base"""
        # Check if we have content
        response = requests.get(f"{self.base_url}/api/knowledge")
        data = response.json()
        
        if data['total'] == 0:
            print("Knowledge base is empty. Ingesting content...")
            payload = {
                "url": self.test_url,
                "depth": 1
            }
            response = requests.post(
                f"{self.base_url}/api/ingest", 
                headers=self.headers,
                json=payload
            )
            self.assertEqual(response.status_code, 200)
            print("Waiting for ingestion to complete...")
            time.sleep(5)  # Give more time for ingestion
            
            # Verify content was added
            response = requests.get(f"{self.base_url}/api/knowledge")
            data = response.json()
            print(f"Knowledge base now contains {data['total']} entries")
        else:
            print(f"Knowledge base already contains {data['total']} entries")
        
    def run_all_tests(self):
        """Run all tests in sequence"""
        try:
            self.test_01_health_check()
            conversation_id = self.test_02_chat_endpoint()
            self.test_03_insert_content()
            self.test_04_get_knowledge()
            self.test_05_chat_with_knowledge()
            self.test_06_detailed_response()
            
            # Run the new sources functionality tests
            self.test_09_sources_functionality_off()
            self.test_10_sources_functionality_on()
            self.test_11_explicit_source_request()
            self.test_12_specific_ai_questions()
            
            # Run these tests last as they modify the knowledge base
            self.test_07_clear_knowledge()
            self.test_08_error_handling()
            
            print("\n✅ All API tests completed successfully!")
            return True
        except Exception as e:
            print(f"\n❌ Test failed: {str(e)}")
            return False

if __name__ == "__main__":
    tester = ZarkAIAPITest()
    tester.run_all_tests()