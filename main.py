from urllib import response
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
import requests
import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Literal, TypedDict
from langchain_ollama import ChatOllama
from langgraph.graph import START,END,StateGraph
load_dotenv()

REPO_OWNER = "hamza-6969"
REPO_NAME = "MULTI_DOCUMENT_RAG_PIPELINE"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
PR_NUMBER = os.getenv("PR_NUMBER")
PR_TITLE = os.getenv("PR_TITLE")

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def get_pull_requests():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/pulls"
    response = requests.get(url, headers=headers)
    return response.json()

def get_pr_files(pr_number):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/pulls/{pr_number}/files"
    response = requests.get(url, headers=headers)
    return response.json()

class error_response(BaseModel):
    error_line: int = Field(..., description="Line number where the error occurs")
    error_message: str = Field(..., description="Description of the error")
    error_correction: str = Field(..., description="Suggested correction for the error")
    severity:Literal["low", "medium", "high"] = Field(..., description="Severity level of the error")

class ReviewResponse(BaseModel):
    errors: list[error_response] = Field(..., description="List of identified errors in the code patch")

def analyze_code(patch_code):
    llm = ChatOllama(model="mistral")
    if patch_code :
        preamble = f"""You are a code review assistant. Your task is to analyze the provided code patch 
        and identify any potential errors, including syntax errors, logical errors, and potential bugs. For each identified error
        """
        structured_llm = llm.with_structured_output(ReviewResponse)
        prompt = ChatPromptTemplate.from_messages([
        ("system", preamble),
        (
            "human",
            "Here is the code patch:\n{patch_code}\nPlease analyze it."
        )
        ])
        
        chain = prompt | structured_llm

        response = chain.invoke({
            "patch_code": patch_code
        })

        return response


class GraphState(TypedDict):
    pr_number: int
    patch_code: str
    analysis_result: ReviewResponse
    high_severity_errors: list[error_response]

def post_comment(GraphState) :
    pr_number = GraphState["pr_number"]
    analysis_result = GraphState["analysis_result"]

    comment_body = "AI Code Review\n\n"
    
    for error in analysis_result.errors:
        comment_body += f"""
    Line: {error.error_line}
    Issue: {error.error_message}
    Fix: {error.error_correction}
    Severity: {error.severity}

    """
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{pr_number}/comments"
    data = {"body": comment_body}
    response = requests.post(url, headers=headers, json=data)
    return GraphState


def pr_files_fetcher(GraphState) :  
    pr_number = GraphState["pr_number"]
    patch_code = []
    files= get_pr_files(pr_number)
    for file in files:
        if "patch" in file:
            patch_code.append(file["patch"])
    GraphState["patch_code"] = "\n".join(patch_code)
    return GraphState

def code_analyzer(GraphState) :
    patch_code = GraphState["patch_code"]
    analysis_result = analyze_code(patch_code)
    GraphState["analysis_result"] = analysis_result
    GraphState["high_severity_errors"] = [error for error in analysis_result.errors if error.severity == "high"]
    return GraphState

def slack_notif(GraphState) :
    analysis_result = GraphState["analysis_result"]
    slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    message = ""
    for error in GraphState["high_severity_errors"]:
        message += f"AI Code Review Alert:\nError Line: {error.error_line}\nError Message: {error.error_message}\nError Correction: {error.error_correction}\nSeverity: {error.severity}\n\n"
    
    payload = {"text": message}
    response = requests.post(slack_webhook_url, json=payload)

    return GraphState

workflow = StateGraph(GraphState)
workflow.add_node("pr_files_fetcher", pr_files_fetcher)
workflow.add_node("code_analyzer", code_analyzer)
workflow.add_node("post_comment", post_comment)
workflow.add_node("slack_notif", slack_notif)
workflow.add_edge(START, "pr_files_fetcher")
workflow.add_edge("pr_files_fetcher", "code_analyzer")
workflow.add_edge("code_analyzer", "slack_notif")
workflow.add_edge("code_analyzer", "post_comment")
workflow.add_edge("slack_notif", END)
workflow.add_edge("post_comment", END)

app = workflow.compile()