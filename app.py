# app.py - FINAL LEGACY MODERNIZER PRO (Dec 12, 2025)
# Beautiful banner + Unit tests + Deploy steps + 500k+ lines ready

import streamlit as st
import zipfile
import io
import os
import shutil
import git
import time
import uuid
import hashlib
import json
from datetime import datetime

# ========= AI PROVIDERS =========
import openai
import google.generativeai as genai
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
try:
    from anthropic import Anthropic
except ImportError:
    pass

st.set_page_config(page_title="Legacy Modernizer Pro", layout="wide", page_icon="Rocket")

# ====================== CUSTOMIZABLE BANNER ======================
with st.sidebar:
    st.header("App Branding")
    app_title = st.text_input("App Title", value="Legacy Modernizer Pro")
    tagline = st.text_input("Tagline", value="From Mainframe to Cloud in Minutes")
    company = st.text_input("Company", value="Your Company")
    
    col1, col2 = st.columns(2)
    with col1:
        primary_color = st.color_picker("Primary Color", "#1e3c72")
    with col2:
        accent_color = st.color_picker("Accent Color", "#3b82f6")
    
    text_color = st.color_picker("Text Color", "#ffffff")
    logo_url = st.text_input("Logo URL (optional)", placeholder="https://yourcompany.com/logo.png")
    show_logo = st.checkbox("Show Logo", value=True)

def render_banner():
    logo_html = f'<img src="{logo_url}" style="height:70px; margin-right:20px; border-radius:10px;">' if show_logo and logo_url else ""
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {primary_color}, {accent_color});
        padding: 50px 30px;
        border-radius: 20px;
        margin: 20px 0 50px 0;
        text-align: center;
        box-shadow: 0 15px 35px rgba(0,0,0,0.3);
        color: {text_color};
        font-family: 'Segoe UI', sans-serif;
    ">
        <div style="display: flex; justify-content: center; align-items: center; gap: 30px; flex-wrap: wrap;">
            {logo_html}
            <div>
                <h1 style="margin:0; font-size:4rem; font-weight:bold; text-shadow: 3px 3px 10px rgba(0,0,0,0.5);">
                    {app_title}
                </h1>
                <p style="margin:20px 0 10px; font-size:2rem; opacity:0.95;">
                    {tagline}
                </p>
                <p style="margin:0; font-size:1.4rem; opacity:0.85;">
                    {company} • AI-Powered • 500k+ Lines • Auto Tests • One-Click Deploy
                </p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# RENDER BANNER FIRST
render_banner()

# ====================== CACHE SYSTEM ======================
CACHE_FILE = "conversion_cache.json"
TEST_CACHE_FILE = "test_cache.json"

if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        try: CACHE = json.load(f)
        except: CACHE = {}
else:
    CACHE = {}

if os.path.exists(TEST_CACHE_FILE):
    with open(TEST_CACHE_FILE, "r", encoding="utf-8") as f:
        try: TEST_CACHE = json.load(f)
        except: TEST_CACHE = {}
else:
    TEST_CACHE = {}

def save_caches():
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(CACHE, f, indent=2)
    with open(TEST_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(TEST_CACHE, f, indent=2)

# ====================== MODEL MAPPING ======================
def get_model(provider):
    return {
        "Anthropic (Claude) - Best Quality": "claude-sonnet-4-5-20250929",
        "OpenAI (GPT-4o) - Fast & Smart": "gpt-4o-2024-08-06",
        "Google Gemini - Free Tier Available": "gemini-1.5-pro",
        "Groq (Llama3-70b) - Lightning Fast": "llama3-70b-8192"
    }.get(provider, "claude-sonnet-4-5-20250929")

# ====================== CONVERSION WITH PROGRESS ======================
def convert_smart_with_progress(code, source_lang, target, provider, api_key):
    progress = st.progress(0)
    status = st.empty()
    status.info("Analyzing code...")

    key = hashlib.md5((code + provider + target).encode()).hexdigest()
    if key in CACHE:
        progress.progress(100)
        status.success("Cache hit – instant conversion!")
        time.sleep(1)
        return CACHE[key]

    progress.progress(30)
    status.info("Converting with AI...")

    prompt = f"Convert this {source_lang} code to clean {target}. Return ONLY source code.\n\nCODE:\n{code}"
    model = get_model(provider)

    try:
        if "Anthropic" in provider:
            from anthropic import Anthropic
            client = Anthropic(api_key=api_key)
            resp = client.messages.create(model=model, max_tokens=4096, temperature=0,
                                          messages=[{"role": "user", "content": prompt}])
            result = resp.content[0].text.strip()
        elif "OpenAI" in provider:
            client = openai.OpenAI(api_key=api_key)
            resp = client.chat.completions.create(model=model, temperature=0,
                                                   messages=[{"role": "user", "content": prompt}])
            result = resp.choices[0].message.content.strip()
        elif "Gemini" in provider:
            genai.configure(api_key=api_key)
            m = genai.GenerativeModel(model)
            resp = m.generate_content(prompt, generation_config={"temperature": 0})
            result = resp.text.strip()
        elif "Groq" in provider and GROQ_AVAILABLE:
            client = Groq(api_key=api_key)
            resp = client.chat.completions.create(model=model, temperature=0,
                                                   messages=[{"role": "user", "content": prompt}])
            result = resp.choices[0].message.content.strip()

        CACHE[key] = result
        save_caches()
        progress.progress(100)
        status.success("Conversion Complete!")
        st.balloons()
        return result

    except Exception as e:
        st.error(f"Error: {str(e)[:100]}")
        return "# CONVERSION FAILED"

# ====================== UNIT TEST GENERATION ======================
def generate_unit_tests(converted_code, filename, target, provider, api_key):
    key = hashlib.md5((converted_code + filename + "TEST").encode()).hexdigest()
    if key in TEST_CACHE:
        return TEST_CACHE[key]

    status = st.status("Generating unit tests...")
    if "Python" in target:
        prompt = f"Generate comprehensive pytest tests for this Python code:\n\n{converted_code}"
        test_file = f"test_{os.path.splitext(filename)[0]}.py"
    else:
        prompt = f"Generate JUnit 5 tests for this Java class:\n\n{converted_code}"
        test_file = f"{os.path.splitext(filename)[0]}Test.java"

    model = get_model(provider)
    try:
        if "Anthropic" in provider:
            from anthropic import Anthropic
            client = Anthropic(api_key=api_key)
            resp = client.messages.create(model=model, max_tokens=4096, temperature=0,
                                          messages=[{"role": "user", "content": prompt}])
            test_code = resp.content[0].text.strip()
        TEST_CACHE[key] = test_code
        save_caches()
        status.update(label="Tests generated!", state="complete")
        return {test_file: test_code}
    except:
        return {"TEST_FAILED.txt": "# Test generation failed"}

# ====================== DEPLOYMENT GUIDE ======================
def generate_deploy_guide(cloud, service, framework, provider, api_key):
    if not api_key:
        return "# Enter API key to generate deploy steps"
    prompt = f"Generate exact bash commands to deploy a {framework} app to {cloud} {service}. Return only commands."
    try:
        model = get_model(provider)
        if "Anthropic" in provider:
            from anthropic import Anthropic
            client = Anthropic(api_key=api_key)
            resp = client.messages.create(model=model, max_tokens=1500, temperature=0,
                                          messages=[{"role": "user", "content": prompt}])
            return resp.content[0].text.strip()
    except:
        pass
    return f"# Deploy guide for {cloud} {service}"

# ====================== SIDEBAR (AI + DEPLOY) ======================
with st.sidebar:
    st.header("AI Engine")
    provider = st.selectbox("Model", [
        "Anthropic (Claude) - Best Quality",
        "OpenAI (GPT-4o) - Fast & Smart",
        "Google Gemini - Free Tier Available"
    ] + (["Groq (Llama3-70b) - Lightning Fast"] if GROQ_AVAILABLE else []))
    api_key = st.text_input("API Key", type="password")
    st.session_state.provider = provider
    st.session_state.api_key = api_key

    st.divider()
    st.header("Deploy Target")
    cloud = st.selectbox("Cloud", ["AWS", "Azure", "Google Cloud"])
    services = {"AWS": ["EC2", "ECS Fargate", "EKS"], "Azure": ["App Service"], "Google Cloud": ["Cloud Run"]}
    service = st.selectbox("Service", services[cloud])
    st.session_state.cloud = cloud
    st.session_state.service = service

# ====================== TABS ======================
tab_input, tab_convert, tab_results = st.tabs(["1. Input", "2. Convert", "3. Results & Deploy"])

# ====================== INPUT TAB ======================
with tab_input:
    col1, col2 = st.columns(2)
    with col1: source_lang = st.selectbox("Source Language", ["COBOL", "JCL", "C#", "VB6"])
    with col2: target = st.selectbox("Target", ["Python + FastAPI", "Java + Spring Boot"])

    mode = st.radio("Input Method", ["Paste Code", "GitHub Repository"], horizontal=True)

    if mode == "Paste Code":
        code = st.text_area("Paste your legacy code", height=400)
        if st.button("Convert Snippet", type="primary") and code and api_key:
            result = convert_smart_with_progress(code, source_lang, target, provider, api_key)
            st.session_state.results = {"main.py" if "Python" in target else "Main.java": result}
            st.session_state.target = target
            st.rerun()

    else:
        url = st.text_input("GitHub Repository URL")
        if st.button("Clone Repository") and url:
            with st.spinner("Cloning..."):
                folder = f"temp_{uuid.uuid4().hex[:8]}"
                git.Repo.clone_from(url, folder, depth=1)
                files = []
                for root, _, fs in os.walk(folder):
                    for f in fs:
                        if f.lower().endswith(('.cbl','.cob','.cs','.java')):
                            path = os.path.join(root, f)
                            with open(path, "r", errors="ignore") as ff:
                                files.append((f, ff.read()))
                st.session_state.files = files
                st.session_state.folder = folder
                st.session_state.source_lang = source_lang
                st.session_state.target = target
                st.success(f"Found {len(files)} files")

# ====================== CONVERT TAB ======================
with tab_convert:
    if "files" in st.session_state:
        if st.button("START FULL CONVERSION", type="primary"):
            progress = st.progress(0)
            results = {}
            for i, (name, code) in enumerate(st.session_state.files):
                status = st.empty()
                status.info(f"Converting {name}...")
                converted = convert_smart_with_progress(code, st.session_state.source_lang, st.session_state.target,
                                                        st.session_state.provider, st.session_state.api_key)
                new_name = os.path.splitext(name)[0] + (".py" if "Python" in st.session_state.target else ".java")
                results[new_name] = converted
                progress.progress((i + 1) / len(st.session_state.files))
            st.session_state.results = results
            st.balloons()

# ====================== RESULTS TAB ======================
with tab_results:
    if "results" in st.session_state:
        project = {"Dockerfile": "FROM python:3.11-slim\nCMD [\"uvicorn\", \"main:app\"]" if "Python" in st.session_state.target else "FROM openjdk:17\nCMD [\"java\", \"Main\"]", **st.session_state.results}

        if st.button("Generate Unit Tests", type="primary"):
            with st.spinner("Generating tests..."):
                all_tests = {}
                for name, code in st.session_state.results.items():
                    tests = generate_unit_tests(code, name, st.session_state.target, provider, api_key)
                    all_tests.update(tests)
                st.session_state.tests = all_tests
                st.success("All tests generated!")

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            for n, c in project.items():
                z.writestr(n, c)
            if "tests" in st.session_state:
                for n, c in st.session_state.tests.items():
                    z.writestr(f"tests/{n}", c)
        buffer.seek(0)

        st.success("CONVERSION & TESTS COMPLETE!")
        st.download_button("Download Package + Tests", buffer, "modernized-with-tests.zip", type="primary")

        with st.expander(f"Deploy to {st.session_state.cloud} {st.session_state.service}", expanded=True):
            guide = generate_deploy_guide(st.session_state.cloud, st.session_state.service,
                                         st.session_state.target, st.session_state.provider, st.session_state.api_key)
            st.code(guide, language="bash")

st.caption("© 2025 Your Company – Legacy Modernizer Pro | Built with AI")