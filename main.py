from urllib import response

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
import requests
import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Literal
from langchain_ollama import ChatOllama
load_dotenv()

REPO_OWNER = "hamza-6969"
REPO_NAME = "MULTI_DOCUMENT_RAG_PIPELINE"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

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

def error_response(BaseModel):
    error_line: int = Field(..., description="Line number where the error occurs")
    error_message: str = Field(..., description="Description of the error")
    error_correction: str = Field(..., description="Suggested correction for the error")
    severity:Literal["low", "medium", "high"] = Field(..., description="Severity level of the error")

def response_model(BaseModel):
    errors: list[error_response] = Field(..., description="List of identified errors in the code")

def analyze_code(patch_code):
    llm = ChatOllama(model="Mistral")
    parser =PydanticOutputParser(pydantic_object=response_model)
    format_instructions = parser.get_format_instructions()
    
    preamble = f"""You are a code review assistant. Your task is to analyze the provided code patch 
    and identify any potential errors, including syntax errors, logical errors, and potential bugs. For each identified error, provide the response in the following format:
    {format_instructions}
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", preamble),("human", f"Here is the code patch:\n{patch_code}\nPlease analyze it and provide your response.")])    
    
    response = prompt | llm | parser.parse
    return response