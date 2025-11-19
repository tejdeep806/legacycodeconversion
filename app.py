import streamlit as st
import openai
import google.generativeai as genai
import anthropic
import networkx as nx
import matplotlib.pyplot as plt
import zipfile
import io
import os
import shutil
import stat
import git
import time
import uuid
import streamlit.components.v1 as components
from pyvis.network import Network

# --- Configuration ---
st.set_page_config(page_title="Enterprise Legacy Modernizer", layout="wide", page_icon="🚀")

# --- WINDOWS FIX: Permission Handler ---
def remove_readonly(func, path, _):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass 

# --- HELPER: CLEANUP TEMP FILES ---
def cleanup_all_temp_folders():
    """Scans current directory and deletes all 'temp_repo_' folders."""
    count = 0
    current_dir = os.getcwd()
    for item in os.listdir(current_dir):
        if os.path.isdir(item) and item.startswith("temp_repo_"):
            try:
                shutil.rmtree(item, onerror=remove_readonly)
                count += 1
            except Exception:
                pass # Skip if locked
    return count

# --- Helper: Deployment Script Generator ---
def generate_deploy_guide(provider, service, app_name="modern-app"):
    """Generates actionable CLI commands for deployment."""
    
    if provider == "AWS":
        if "EC2" in service:
            return f"""#!/bin/bash
# --- AWS EC2 DEPLOYMENT STEPS ---
echo "Step 1: Copying files to Server..."
scp -i my-key.pem {app_name}.zip ec2-user@your-ec2-ip:/home/ec2-user/

echo "Step 2: Connecting to Server..."
ssh -i my-key.pem ec2-user@your-ec2-ip << 'EOF'
    sudo yum update -y
    sudo yum install docker -y
    sudo service docker start
    sudo usermod -a -G docker ec2-user

    unzip {app_name}.zip
    cd {app_name}
    docker build -t {app_name} .
    
    # Run in background
    docker run -d {app_name}
EOF
echo "✅ Deployment Complete!"
"""
        elif "EKS" in service:
            return f"""#!/bin/bash
# --- AWS EKS (KUBERNETES) DEPLOYMENT STEPS ---
APP_NAME="{app_name}"
AWS_REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URL="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URL

docker build -t $APP_NAME .
docker tag $APP_NAME:latest $ECR_URL/$APP_NAME:v1
docker push $ECR_URL/$APP_NAME:v1

kubectl create deployment $APP_NAME --image=$ECR_URL/$APP_NAME:v1
# Note: If this is a standard script (not a web server), you do not need 'kubectl expose'
echo "✅ Pods deployed!"
"""

    elif provider == "Azure":
        if "App Service" in service:
            return f"""#!/bin/bash
# --- AZURE APP SERVICE ---
az login
az webapp up --name {app_name} --resource-group ModernizationGroup --runtime "PYTHON:3.9" --sku B1
"""
    elif provider == "Google Cloud":
        return f"""#!/bin/bash
# --- GOOGLE CLOUD RUN ---
gcloud builds submit --tag gcr.io/my-project/{app_name}
gcloud run deploy {app_name} --image gcr.io/my-project/{app_name} --platform managed --region us-central1
"""
    return "# Select a specific provider in the sidebar."

# --- Helper: File & Repo Logic ---
def clone_repository(repo_url):
    unique_id = str(uuid.uuid4())[:8]
    temp_dir = f"temp_repo_{unique_id}"
    # We do NOT auto-delete old ones here to prevent "WinError 32"
    # We use the new Manual Cleanup button instead.
    try:
        git.Repo.clone_from(repo_url, temp_dir, multi_options=["-c core.longpaths=true"], allow_unsafe_options=True)
        return temp_dir, None
    except Exception as e:
        return None, str(e)

def get_all_files(root_dir, extensions=[".cbl", ".cob", ".jcl", ".cs", ".vb", ".f90", ".c", ".py", ".java"]):
    file_list = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if any(file.lower().endswith(ext) for ext in extensions):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, root_dir)
                file_list.append((rel_path, full_path))
    return file_list

def build_dependency_graph(file_list):
    G = nx.DiGraph()
    for rel_path, full_path in file_list:
        short_name = os.path.basename(rel_path)
        G.add_node(short_name, title=rel_path)
        try:
            with open(full_path, "r", errors="ignore") as f: content = f.read().lower()
            for other_rel, _ in file_list:
                other_short = os.path.basename(other_rel)
                if other_short == short_name: continue
                if os.path.splitext(other_short)[0].lower() in content:
                    G.add_edge(short_name, other_short)
        except: pass
    return G

# --- AI Wrappers ---
def call_ai(code, context, provider, key, model, target):
    if "Offline" in provider or not key:
        time.sleep(0.1)
        return f"# Offline Conversion ({target})\n# Logic preserved.\ndef main():\n    print('Converted')"
    
    # Customize prompt based on "Standard" vs "Microservice"
    style_instruction = "Create a standard, standalone script/class. Do NOT use web frameworks (like FastAPI/Spring) unless necessary." if "Standard" in target else "Create a production-ready Microservice (FastAPI/Spring Boot)."

    prompt = f"""Act as a Senior Architect. Convert this legacy code to {target}.
    STYLE GUIDE: {style_instruction}
    CONTEXT: {context[:2000] if context else "None"}
    CODE: {code}
    INSTRUCTIONS: Return ONLY valid source code. No markdown."""
    
    try:
        if "Anthropic" in provider:
            client = anthropic.Anthropic(api_key=key)
            return client.messages.create(model=model, max_tokens=4096, messages=[{"role": "user", "content": prompt}]).content[0].text
        elif "Gemini" in provider:
            genai.configure(api_key=key)
            return genai.GenerativeModel(model).generate_content(prompt).text
        elif "OpenAI" in provider:
            client = openai.OpenAI(api_key=key)
            return client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}]).choices[0].message.content
    except Exception as e: return f"# Error: {str(e)}"

# --- Sidebar ---
with st.sidebar:
    st.header("🧠 AI Engine")
    provider = st.selectbox("Provider", ["Anthropic (Best)", "OpenAI", "Google Gemini", "Offline"])
    api_key = ""; model_name = ""
    if "Anthropic" in provider:
        api_key = st.text_input("Anthropic Key", type="password")
        model_name = st.selectbox("Model", ["claude-sonnet-4-5-20250929", "claude-3-5-sonnet-20241022"]).split(" ")[0]
    elif "OpenAI" in provider:
        api_key = st.text_input("OpenAI Key", type="password"); model_name = "gpt-4o"
    elif "Gemini" in provider:
        api_key = st.text_input("Gemini Key", type="password"); model_name = "gemini-1.5-flash"

    st.divider()
    
    # --- NEW CLEANUP BUTTON ---
    if st.button("🗑️ Clear Temp Cache"):
        deleted = cleanup_all_temp_folders()
        st.toast(f"Cleaned up {deleted} temporary folders!", icon="🧹")

    st.divider()
    st.header("☁️ Deployment Target")
    cloud_provider = st.selectbox("Cloud Provider", ["AWS", "Azure", "Google Cloud"])
    svc_options = []
    if cloud_provider == "AWS": svc_options = ["EC2 (VM)", "EKS (K8s)", "ECS (Fargate)"]
    elif cloud_provider == "Azure": svc_options = ["App Service", "AKS (K8s)"]
    else: svc_options = ["Cloud Run", "GKE"]
    cloud_service = st.selectbox("Service", svc_options)

# --- Main UI ---
st.title("🚀 Universal Legacy Modernizer")
st.markdown("Convert **Code Snippets** OR **Entire Repositories** -> **Deployable Cloud Artifacts**.")

tab_input, tab_preview, tab_results = st.tabs(["1. Input Source", "2. Analysis & Options", "3. Results & Deploy"])

# --- TAB 1: INPUT ---
with tab_input:
    input_mode = st.radio("Select Input Method", ["Paste Code / Single File", "GitHub Repository"], horizontal=True)
    
    if input_mode == "Paste Code / Single File":
        source_lang = st.selectbox("Source Language", ["COBOL", "C#", "Fortran", "JCL"])
        source_code = st.text_area("Paste Legacy Code", value="IDENTIFICATION DIVISION.\nPROGRAM-ID. TEST.\nPROCEDURE DIVISION.\nDISPLAY 'Hello'.\nSTOP RUN.", height=300)
        if st.button("Analyze Snippet"):
            st.session_state['mode'] = 'single'
            st.session_state['source_data'] = {'main.cbl': source_code}
            st.success("Snippet Loaded. Go to 'Analysis' tab.")
            if 'final_results' in st.session_state: del st.session_state['final_results']
            
    else:
        repo_url = st.text_input("GitHub Repo URL")
        if st.button("Clone & Analyze"):
            with st.spinner("Cloning..."):
                repo_dir, err = clone_repository(repo_url)
                if err: st.error(f"Error: {err}")
                else:
                    files = get_all_files(repo_dir)
                    G = build_dependency_graph(files)
                    st.session_state['mode'] = 'repo'
                    st.session_state['repo_files'] = files
                    st.session_state['repo_dir'] = repo_dir
                    st.session_state['graph'] = G
                    st.success(f"Cloned {len(files)} files. Go to 'Analysis' tab.")
                    if 'final_results' in st.session_state: del st.session_state['final_results']

# --- TAB 2: ANALYSIS ---
with tab_preview:
    target_lang = st.selectbox("Target Language", [
        "Python (FastAPI Microservice)", 
        "Python (Standard Script)", 
        "Java (Spring Boot Microservice)",
        "Java (Standard Class)"
    ])
    
    if 'mode' in st.session_state:
        if st.session_state['mode'] == 'repo':
            graph_col, info_col = st.columns([2, 1])
            with info_col:
                st.write("**Dependency Summary**")
                G = st.session_state.get('graph', nx.DiGraph())
                if G.number_of_nodes() > 0:
                    degrees = sorted(G.degree, key=lambda x: x[1], reverse=True)[:5]
                    st.info(f"Detected {G.number_of_nodes()} modules.")
                    for node, degree in degrees:
                        if degree > 0: st.write(f"🔗 **{node}** ({degree} links)")
                else: st.info("No explicit dependencies.")
                st.divider()
                st.dataframe([os.path.basename(f[0]) for f in st.session_state['repo_files']], column_config={"0": "Filename"}, height=200)

            with graph_col:
                st.write("**Interactive Map**")
                G = st.session_state.get('graph', nx.DiGraph())
                if G.number_of_nodes() > 0:
                    try:
                        nt = Network(height="400px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)
                        nt.from_nx(G)
                        nt.force_atlas_2based()
                        path = os.path.join(os.getcwd(), "temp_graph.html")
                        nt.save_graph(path)
                        with open(path, 'r', encoding='utf-8') as f: html_string = f.read()
                        components.html(html_string, height=400, scrolling=True)
                    except: st.warning("Graph too complex to render interactively.")
        else:
            st.code(list(st.session_state['source_data'].values())[0])
            
        st.divider()
        if st.button("🚀 Start Conversion Process", type="primary"):
            st.session_state['trigger_conversion'] = True 
    else:
        st.info("Please load data in the Input tab first.")

# --- TAB 3: RESULTS ---
with tab_results:
    if st.session_state.get('trigger_conversion'):
        status_container = st.empty()
        
        with status_container.container():
            st.subheader("🔄 Modernization in Progress...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            results = {}
            
            # A. Conversion Logic
            if st.session_state['mode'] == 'single':
                status_text.write("Converting Single File...")
                progress_bar.progress(20)
                code = list(st.session_state['source_data'].values())[0]
                conv = call_ai(code, "", provider, api_key, model_name, target_lang)
                
                ext = "java" if "Java" in target_lang else "py"
                fname = "Main" if "Java" in target_lang else "main"
                results[f"{fname}.{ext}"] = conv
                progress_bar.progress(100)
            else:
                files = st.session_state['repo_files']
                total = len(files)
                if not files: progress_bar.progress(100)
                for i, (rel, full) in enumerate(files):
                    short = os.path.basename(rel)
                    status_text.markdown(f"Converting **{short}**...")
                    with open(full, "r", errors="ignore") as f: content = f.read()
                    conv = call_ai(content, "", provider, api_key, model_name, target_lang)
                    new_name = os.path.splitext(short)[0] + (".py" if "Python" in target_lang else ".java")
                    results[new_name] = conv
                    progress_bar.progress(int((i+1)/total*100))
            
            # B. Artifacts
            dockerfile = ""
            reqs_txt = ""
            
            if "FastAPI" in target_lang:
                dockerfile = "FROM python:3.9-slim\nCOPY . /app\nWORKDIR /app\nRUN pip install -r requirements.txt\nCMD ['uvicorn', 'main:app', '--host', '0.0.0.0']"
                reqs_txt = "fastapi\nuvicorn\nrequests"
            elif "Standard Script" in target_lang:
                dockerfile = "FROM python:3.9-slim\nCOPY . /app\nWORKDIR /app\nCMD ['python', 'main.py']"
                reqs_txt = "requests" 
            elif "Spring Boot" in target_lang:
                dockerfile = "FROM openjdk:17\nCOPY . /app\nCMD ['java', '-jar', 'app.jar']"
            elif "Standard Class" in target_lang:
                dockerfile = "FROM openjdk:17\nCOPY . /app\nWORKDIR /app\nRUN javac Main.java\nCMD ['java', 'Main']"

            deploy_script = generate_deploy_guide(cloud_provider, cloud_service)
            
            st.session_state['final_results'] = results
            st.session_state['final_docker'] = dockerfile
            st.session_state['final_deploy'] = deploy_script
            st.session_state['final_reqs'] = reqs_txt
            
            st.session_state['trigger_conversion'] = False 
            
        status_container.empty()
        st.rerun()

    # --- RENDER RESULTS ---
    if 'final_results' in st.session_state:
        results = st.session_state['final_results']
        deploy_script = st.session_state['final_deploy']
        
        st.success(f"✅ Conversion to {target_lang} Complete!")

        st.subheader(f"☁️ Deployment Instructions: {cloud_provider}")
        with st.expander("📖 Click to view Step-by-Step Guide", expanded=True):
            st.info(f"Follow these steps to deploy to **{cloud_service}**:")
            st.code(deploy_script, language="bash")

        st.divider()
        st.subheader("📦 Code Artifacts")
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Converted Logic (Preview)**")
            st.code(list(results.values())[0], language="python" if "Python" in target_lang else "java")
        with c2:
            st.write("**Generated Dockerfile**")
            st.code(st.session_state['final_docker'], language="dockerfile")

        st.divider()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
            for fname, fcode in results.items(): z.writestr(f"src/{fname}", fcode)
            z.writestr("Dockerfile", st.session_state['final_docker'])
            z.writestr("deploy.sh", deploy_script)
            z.writestr("requirements.txt", st.session_state.get('final_reqs', ""))
            z.writestr("README.md", f"# Modernized App\nTarget: {target_lang}")
        buffer.seek(0)
        
        st.download_button(
            label="⬇️ Download Complete Deployment Package (.zip)",
            data=buffer,
            file_name="modernized_cloud_app.zip",
            mime="application/zip",
            type="primary"
        )
    else:
        st.info("Please go to the 'Analysis' tab and click 'Start Conversion'.")