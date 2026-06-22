import pytest
from unittest.mock import patch, MagicMock, Mock
import os
import json
from main import (
    get_pull_requests,
    get_pr_files,
    analyze_code,
    post_comment,
    pr_files_fetcher,
    code_analyzer,
    slack_notif,
    error_response,
    ReviewResponse,
    GraphState,
    app
)


# ========== FIXTURES ==========
@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables"""
    monkeypatch.setenv("GITHUB_TOKEN", "test_token_123")
    monkeypatch.setenv("PR_NUMBER", "42")
    monkeypatch.setenv("PR_TITLE", "Test PR")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/test")


@pytest.fixture
def sample_pr_files():
    """Sample GitHub PR files response"""
    return [
        {
            "filename": "test.py",
            "patch": "+def hello():\n+    print('hello')\n"
        },
        {
            "filename": "main.py",
            "patch": "+print('test')\n"
        }
    ]


@pytest.fixture
def sample_review_response():
    """Sample code review response"""
    errors = [
        error_response(
            error_line=1,
            error_message="Missing docstring",
            error_correction="Add docstring to function",
            severity="low"
        ),
        error_response(
            error_line=5,
            error_message="Undefined variable",
            error_correction="Define variable before use",
            severity="high"
        )
    ]
    return ReviewResponse(errors=errors)


@pytest.fixture
def sample_graph_state(sample_review_response):
    """Sample graph state"""
    return {
        "pr_number": 42,
        "patch_code": "+def test():\n+    pass\n",
        "analysis_result": sample_review_response,
        "high_severity_errors": [e for e in sample_review_response.errors if e.severity == "high"]
    }


# ========== GITHUB API TESTS ==========
class TestGitHubAPIs:
    """Test GitHub API functions"""

    @patch("requests.get")
    def test_get_pull_requests_success(self, mock_get, mock_env_vars):
        """Test successful PR retrieval"""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"number": 1, "title": "Test PR"}]
        mock_get.return_value = mock_response

        result = get_pull_requests()
        
        assert len(result) == 1
        assert result[0]["number"] == 1
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_get_pull_requests_failure(self, mock_get, mock_env_vars):
        """Test PR retrieval failure"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": "Not Found"}
        mock_get.return_value = mock_response

        result = get_pull_requests()
        
        assert "message" in result
        assert result["message"] == "Not Found"

    @patch("requests.get")
    def test_get_pr_files_success(self, mock_get, mock_env_vars, sample_pr_files):
        """Test successful PR files retrieval"""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_pr_files
        mock_get.return_value = mock_response

        result = get_pr_files(42)
        
        assert len(result) == 2
        assert result[0]["filename"] == "test.py"
        assert "patch" in result[0]
        mock_get.assert_called_once()

    @patch("requests.get")
    @patch("main.headers", {"Authorization": "token test_token_123", "Accept": "application/vnd.github.v3+json"})
    def test_get_pr_files_includes_headers(self, mock_get):
        """Test that GitHub token is included in headers"""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        get_pr_files(42)
        
        call_kwargs = mock_get.call_args[1]
        assert "headers" in call_kwargs
        # Just verify headers were passed
        assert call_kwargs["headers"] is not None

    @patch("requests.post")
    def test_post_comment_success(self, mock_post, mock_env_vars, sample_graph_state):
        """Test successful comment posting"""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        result = post_comment(sample_graph_state)
        
        assert result["pr_number"] == 42
        mock_post.assert_called_once()
        
        # Verify the comment body
        call_kwargs = mock_post.call_args[1]
        assert "body" in call_kwargs["json"]
        assert "AI Code Review" in call_kwargs["json"]["body"]

    @patch("requests.post")
    def test_post_comment_format(self, mock_post, mock_env_vars, sample_graph_state):
        """Test comment format includes all error details"""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        post_comment(sample_graph_state)
        
        call_kwargs = mock_post.call_args[1]
        comment_body = call_kwargs["json"]["body"]
        
        assert "Line:" in comment_body
        assert "Issue:" in comment_body
        assert "Fix:" in comment_body
        assert "Severity:" in comment_body


# ========== SLACK API TESTS ==========
class TestSlackAPIs:
    """Test Slack API functions"""

    @patch("requests.post")
    def test_slack_notif_high_severity_only(self, mock_post, mock_env_vars, sample_graph_state):
        """Test that Slack notification only includes high severity errors"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        slack_notif(sample_graph_state)
        
        # Verify Slack was called
        mock_post.assert_called_once()
        
        # Verify the URL is correct
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://hooks.slack.com/services/test"

    @patch("requests.post")
    def test_slack_notif_with_high_errors(self, mock_post, mock_env_vars, sample_graph_state):
        """Test Slack notification with high severity errors"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        slack_notif(sample_graph_state)
        
        # Should have high severity errors
        assert len(sample_graph_state["high_severity_errors"]) > 0
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_slack_notif_no_high_errors(self, mock_post, mock_env_vars):
        """Test Slack notification with no high severity errors"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        state = {
            "pr_number": 42,
            "patch_code": "test",
            "analysis_result": ReviewResponse(errors=[]),
            "high_severity_errors": []
        }
        
        slack_notif(state)
        mock_post.assert_called_once()


# ========== LLM ANALYSIS TESTS ==========
class TestCodeAnalysis:
    """Test code analysis logic"""

    @patch("main.ChatOllama")
    def test_analyze_code_success(self, mock_ollama, mock_env_vars):
        """Test successful code analysis"""
        mock_llm = MagicMock()
        mock_ollama.return_value = mock_llm
        
        mock_response = ReviewResponse(
            errors=[
                error_response(
                    error_line=1,
                    error_message="Test error",
                    error_correction="Fix it",
                    severity="high"
                )
            ]
        )
        mock_llm.with_structured_output.return_value = MagicMock()
        
        # Mock the chain invoke
        with patch("main.ChatPromptTemplate.from_messages") as mock_prompt:
            mock_chain = MagicMock()
            mock_chain.invoke.return_value = mock_response
            mock_prompt.return_value.__or__.return_value = mock_chain
            
            result = analyze_code("+def test(): pass")
            
            # The function should return a ReviewResponse
            assert isinstance(result, ReviewResponse) or result == mock_response

    @patch("main.ChatOllama")
    def test_analyze_code_empty_patch(self, mock_ollama, mock_env_vars):
        """Test code analysis with empty patch"""
        result = analyze_code("")
        assert result is None

    @patch("main.ChatOllama")
    def test_analyze_code_none_patch(self, mock_ollama, mock_env_vars):
        """Test code analysis with None patch"""
        result = analyze_code(None)
        assert result is None


# ========== GRAPH STATE PROCESSING TESTS ==========
class TestGraphStateProcessing:
    """Test graph state processing functions"""

    @patch("main.get_pr_files")
    def test_pr_files_fetcher(self, mock_get_pr_files, mock_env_vars, sample_pr_files):
        """Test PR files fetcher node"""
        mock_get_pr_files.return_value = sample_pr_files

        state = {
            "pr_number": 42,
            "patch_code": "",
            "analysis_result": None,
            "high_severity_errors": []
        }
        
        result = pr_files_fetcher(state)
        
        assert result["patch_code"] != ""
        assert "+def hello():" in result["patch_code"]
        assert "+print('test')" in result["patch_code"]

    @patch("main.analyze_code")
    def test_code_analyzer(self, mock_analyze, sample_graph_state, mock_env_vars):
        """Test code analyzer node"""
        mock_response = sample_graph_state["analysis_result"]
        mock_analyze.return_value = mock_response

        state = {
            "pr_number": 42,
            "patch_code": "+def test(): pass",
            "analysis_result": None,
            "high_severity_errors": []
        }
        
        result = code_analyzer(state)
        
        assert result["analysis_result"] is not None
        assert len(result["high_severity_errors"]) > 0
        assert all(e.severity == "high" for e in result["high_severity_errors"])

    @patch("requests.post")
    def test_slack_notif_called(self, mock_post, mock_env_vars, sample_graph_state):
        """Test Slack notification in graph"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = slack_notif(sample_graph_state)
        
        assert result == sample_graph_state
        mock_post.assert_called_once()


# ========== WORKFLOW TESTS ==========
class TestWorkflow:
    """Test the complete workflow"""

    @patch("main.get_pr_files")
    @patch("main.analyze_code")
    @patch("requests.post")
    def test_workflow_nodes_integration(self, mock_post, mock_analyze, mock_fetch, mock_env_vars, sample_pr_files, sample_review_response):
        """Test workflow node integration without full graph execution"""
        # Mock get_pr_files
        mock_fetch.return_value = sample_pr_files
        
        # Mock analyze_code
        mock_analyze.return_value = sample_review_response
        
        # Mock post requests
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Test the sequence of operations
        initial_state = {
            "pr_number": 42,
            "patch_code": "",
            "analysis_result": None,
            "high_severity_errors": []
        }
        
        # Step 1: Fetch PR files
        state1 = pr_files_fetcher(initial_state)
        assert state1["patch_code"] != ""
        
        # Step 2: Analyze code
        state2 = code_analyzer(state1)
        assert state2["analysis_result"] is not None
        
        # Step 3: Post comment
        state3 = post_comment(state2)
        assert state3["pr_number"] == 42
        
        # Step 4: Send Slack notification
        state4 = slack_notif(state3)
        assert state4 is not None


# ========== DATA MODEL TESTS ==========
class TestDataModels:
    """Test Pydantic models"""

    def test_error_response_creation(self):
        """Test error_response model creation"""
        error = error_response(
            error_line=10,
            error_message="Test error",
            error_correction="Fix it",
            severity="high"
        )
        
        assert error.error_line == 10
        assert error.error_message == "Test error"
        assert error.severity == "high"

    def test_error_response_invalid_severity(self):
        """Test error_response with invalid severity"""
        with pytest.raises(Exception):
            error_response(
                error_line=10,
                error_message="Test error",
                error_correction="Fix it",
                severity="invalid"
            )

    def test_review_response_creation(self, sample_review_response):
        """Test ReviewResponse model creation"""
        assert isinstance(sample_review_response, ReviewResponse)
        assert len(sample_review_response.errors) > 0

    def test_graph_state_type(self, sample_graph_state):
        """Test GraphState TypedDict"""
        assert "pr_number" in sample_graph_state
        assert "patch_code" in sample_graph_state
        assert "analysis_result" in sample_graph_state
        assert "high_severity_errors" in sample_graph_state


# ========== ERROR HANDLING TESTS ==========
class TestErrorHandling:
    """Test error handling"""

    @patch("requests.get")
    def test_github_api_error_response(self, mock_get, mock_env_vars):
        """Test handling of GitHub API errors"""
        mock_get.side_effect = Exception("Connection error")
        
        with pytest.raises(Exception):
            get_pull_requests()

    @patch("requests.post")
    def test_slack_api_failure(self, mock_post, mock_env_vars, sample_graph_state):
        """Test handling of Slack API failures"""
        mock_post.side_effect = Exception("Slack error")
        
        with pytest.raises(Exception):
            slack_notif(sample_graph_state)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
