"""
Test suite for Reel Creator API endpoints
Tests: Voices endpoint, Script generation endpoint
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://live-support-test.preview.emergentagent.com')


class TestReelCreatorVoicesAPI:
    """Tests for GET /api/admin/ai-studio/voices endpoint"""
    
    def test_voices_endpoint_returns_200(self):
        """Verify voices endpoint returns 200 status"""
        response = requests.get(f"{BASE_URL}/api/admin/ai-studio/voices")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Voices endpoint returns 200")
    
    def test_voices_endpoint_returns_success(self):
        """Verify voices endpoint returns success=True"""
        response = requests.get(f"{BASE_URL}/api/admin/ai-studio/voices")
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data.get('success')}"
        print("✓ Voices endpoint returns success=True")
    
    def test_voices_endpoint_has_voices_list(self):
        """Verify voices endpoint returns voices list"""
        response = requests.get(f"{BASE_URL}/api/admin/ai-studio/voices")
        data = response.json()
        assert "voices" in data, "Response missing 'voices' key"
        assert isinstance(data["voices"], list), "voices should be a list"
        assert len(data["voices"]) > 0, "voices list should not be empty"
        print(f"✓ Voices endpoint returns {len(data['voices'])} voices")
    
    def test_voices_have_openai_voices(self):
        """Verify OpenAI voices are available (free voices)"""
        response = requests.get(f"{BASE_URL}/api/admin/ai-studio/voices")
        data = response.json()
        
        openai_voices = [v for v in data["voices"] if v.get("category") == "openai_free"]
        assert len(openai_voices) >= 9, f"Expected at least 9 OpenAI voices, got {len(openai_voices)}"
        
        # Check required OpenAI voices
        voice_ids = [v["voice_id"] for v in openai_voices]
        expected_voices = ["onyx", "nova", "alloy", "echo", "fable", "shimmer", "coral", "sage", "ash"]
        for voice in expected_voices:
            assert voice in voice_ids, f"Missing OpenAI voice: {voice}"
        
        print(f"✓ All 9 OpenAI voices available: {voice_ids}")
    
    def test_voices_have_elevenlabs_voices(self):
        """Verify ElevenLabs voices are available (paid voices)"""
        response = requests.get(f"{BASE_URL}/api/admin/ai-studio/voices")
        data = response.json()
        
        elevenlabs_voices = [v for v in data["voices"] if v.get("category") == "elevenlabs_paid"]
        assert len(elevenlabs_voices) >= 5, f"Expected at least 5 ElevenLabs voices, got {len(elevenlabs_voices)}"
        
        print(f"✓ {len(elevenlabs_voices)} ElevenLabs voices available")
    
    def test_voices_have_correct_structure(self):
        """Verify each voice has required fields"""
        response = requests.get(f"{BASE_URL}/api/admin/ai-studio/voices")
        data = response.json()
        
        required_fields = ["voice_id", "name", "description", "category", "free"]
        for voice in data["voices"]:
            for field in required_fields:
                assert field in voice, f"Voice missing required field: {field}"
        
        print("✓ All voices have correct structure (voice_id, name, description, category, free)")
    
    def test_voices_free_voices_list(self):
        """Verify free_voices list is returned"""
        response = requests.get(f"{BASE_URL}/api/admin/ai-studio/voices")
        data = response.json()
        
        assert "free_voices" in data, "Response missing 'free_voices' key"
        assert isinstance(data["free_voices"], list), "free_voices should be a list"
        assert len(data["free_voices"]) >= 9, f"Expected at least 9 free voices, got {len(data['free_voices'])}"
        
        print(f"✓ {len(data['free_voices'])} free voices listed")


class TestReelCreatorScriptGenerationAPI:
    """Tests for POST /api/admin/ai-studio/generate-reel-script endpoint"""
    
    def test_script_generation_returns_200(self):
        """Verify script generation endpoint returns 200 status"""
        payload = {
            "topic": "Why PDRN is revolutionary for skincare",
            "tone": "founder",
            "duration": "30",
            "language": "en"
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/ai-studio/generate-reel-script",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Script generation endpoint returns 200")
    
    def test_script_generation_returns_success(self):
        """Verify script generation endpoint returns success=True"""
        payload = {
            "topic": "The science behind salmon DNA",
            "tone": "scientific",
            "duration": "30",
            "language": "en"
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/ai-studio/generate-reel-script",
            json=payload
        )
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        print("✓ Script generation returns success=True")
    
    def test_script_generation_returns_script(self):
        """Verify script generation returns a non-empty script"""
        payload = {
            "topic": "3 mistakes people make with retinol",
            "tone": "casual",
            "duration": "30",
            "language": "en"
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/ai-studio/generate-reel-script",
            json=payload
        )
        data = response.json()
        
        assert "script" in data, "Response missing 'script' key"
        assert isinstance(data["script"], str), "script should be a string"
        assert len(data["script"]) > 20, f"Script too short: {len(data['script'])} chars"
        
        print(f"✓ Script generated with {len(data['script'])} characters")
    
    def test_script_generation_returns_word_count(self):
        """Verify script generation returns word count"""
        payload = {
            "topic": "How to layer skincare products",
            "tone": "professional",
            "duration": "30",
            "language": "en"
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/ai-studio/generate-reel-script",
            json=payload
        )
        data = response.json()
        
        assert "word_count" in data, "Response missing 'word_count' key"
        assert isinstance(data["word_count"], int), "word_count should be an integer"
        assert data["word_count"] > 0, "word_count should be positive"
        
        print(f"✓ Word count returned: {data['word_count']}")
    
    def test_script_generation_returns_estimated_duration(self):
        """Verify script generation returns estimated duration"""
        payload = {
            "topic": "Morning skincare routine",
            "tone": "casual",
            "duration": "30",
            "language": "en"
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/ai-studio/generate-reel-script",
            json=payload
        )
        data = response.json()
        
        assert "estimated_duration_seconds" in data, "Response missing 'estimated_duration_seconds' key"
        assert isinstance(data["estimated_duration_seconds"], (int, float)), "estimated_duration should be a number"
        
        print(f"✓ Estimated duration returned: {data['estimated_duration_seconds']}s")
    
    def test_script_generation_with_product_name(self):
        """Verify script generation works with product_name"""
        payload = {
            "topic": "Product spotlight",
            "product_name": "AURA-GEN PDRN Serum",
            "tone": "founder",
            "duration": "30",
            "language": "en"
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/ai-studio/generate-reel-script",
            json=payload
        )
        data = response.json()
        
        assert data.get("success") == True, f"Expected success=True with product_name"
        assert len(data.get("script", "")) > 20, "Script should be generated with product_name"
        
        print("✓ Script generation works with product_name parameter")
    
    def test_script_generation_different_tones(self):
        """Verify script generation works with all tone options"""
        tones = ["founder", "professional", "casual", "scientific"]
        
        for tone in tones:
            payload = {
                "topic": "Skincare tips",
                "tone": tone,
                "duration": "15",
                "language": "en"
            }
            response = requests.post(
                f"{BASE_URL}/api/admin/ai-studio/generate-reel-script",
                json=payload
            )
            data = response.json()
            
            assert data.get("success") == True, f"Script generation failed for tone: {tone}"
            print(f"  ✓ Tone '{tone}' works")
        
        print("✓ All tones work: founder, professional, casual, scientific")
    
    def test_script_generation_different_durations(self):
        """Verify script generation works with different durations"""
        durations = ["15", "30", "60", "90"]
        
        for duration in durations:
            payload = {
                "topic": "Quick skincare tips",
                "tone": "casual",
                "duration": duration,
                "language": "en"
            }
            response = requests.post(
                f"{BASE_URL}/api/admin/ai-studio/generate-reel-script",
                json=payload
            )
            data = response.json()
            
            assert data.get("success") == True, f"Script generation failed for duration: {duration}"
            print(f"  ✓ Duration '{duration}s' works")
        
        print("✓ All durations work: 15, 30, 60, 90 seconds")
    
    def test_script_generation_hinglish_language(self):
        """Verify script generation works with Hinglish language"""
        payload = {
            "topic": "Skincare routine for Indian skin",
            "tone": "founder",
            "duration": "30",
            "language": "hi"
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/ai-studio/generate-reel-script",
            json=payload
        )
        data = response.json()
        
        assert data.get("success") == True, "Script generation failed for Hinglish"
        assert len(data.get("script", "")) > 20, "Script should be generated in Hinglish"
        
        print("✓ Hinglish (hi) language option works")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
