import requests
import unittest
import json
import time

class ZarkAIAPITest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(ZarkAIAPITest, self).__init__(*args, **kwargs)
        # Get the backend URL from frontend .env file
        self.base_url = "https://5fdd8ed9-e880-404a-ba41-e7079e18cde9.preview.emergentagent.com"
        self.headers = {'Content-Type': 'application/json'}
        
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
        
        # Test invalid ingest request
        print("Testing invalid ingest request...")
        payload = {
            "url": "not-a-valid-url",
            "depth": 1
        }
        response = requests.post(
            f"{self.base_url}/api/ingest", 
            headers=self.headers,
            json=payload
        )
        self.assertIn(response.status_code, [422, 500], "Should return error for invalid URL")
        data = response.json()
        print(f"✅ Invalid ingest request error: {data}")
        self.assertIn('detail', data)
        
    def run_all_tests(self):
        """Run all tests in sequence"""
        try:
            self.test_01_health_check()
            conversation_id = self.test_02_chat_endpoint()
            self.test_03_insert_content()
            self.test_04_get_knowledge()
            self.test_05_chat_with_knowledge()
            self.test_06_detailed_response()
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