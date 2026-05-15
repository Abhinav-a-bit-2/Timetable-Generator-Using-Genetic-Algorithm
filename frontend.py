# pyrefly: ignore [missing-import]
import gradio as gr
import requests
import pandas as pd
import os

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

def get_stats():
    try:
        response = requests.get(f"{BACKEND_URL}/stats")
        if response.status_code == 200:
            stats = response.json()
            return f"Branches: {stats['branches']} | Courses: {stats['courses']} | Teachers: {stats['teachers']}"
        return "Could not fetch stats"
    except:
        return "Backend not reachable"

def init_database():
    try:
        response = requests.post(f"{BACKEND_URL}/initialize")
        return response.json().get("message", "Success")
    except Exception as e:
        return f"Error: {str(e)}"

def add_course(code, name, branch):
    try:
        response = requests.post(f"{BACKEND_URL}/courses", params={
            "course_code": code,
            "course_name": name,
            "branch_name": branch
        })
        return response.json().get("message", "Success")
    except Exception as e:
        return f"Error: {str(e)}"

def generate_timetable(generations):
    try:
        response = requests.post(f"{BACKEND_URL}/generate", params={"generations": generations})
        if response.status_code == 200:
            data = response.json()
            if data["status"] == "success":
                return pd.DataFrame(data["data"]), "✅ Generation Complete!"
            return None, f"Error: {data.get('detail', 'Unknown error')}"
        return None, f"Error: {response.text}"
    except Exception as e:
        return None, f"Exception: {str(e)}"

def get_current_timetable():
    try:
        response = requests.get(f"{BACKEND_URL}/timetable")
        if response.status_code == 200:
            data = response.json()
            if data:
                return pd.DataFrame(data)
            return pd.DataFrame(columns=["No data found"])
        return pd.DataFrame(columns=["Error fetching data"])
    except Exception as e:
        return pd.DataFrame(columns=[f"Exception: {str(e)}"])

def get_branches():
    try:
        response = requests.get(f"{BACKEND_URL}/branches")
        return response.json()
    except:
        return []

# UI Theme and Layout
with gr.Blocks(title="Timetable Generator") as demo:
    gr.Markdown("# 🗓️ Institutional Timetable Generator")
    
    # ... (rest of the blocks code remains same)
    # I'll just replace the whole block for safety

    with gr.Row():
        stats_box = gr.Textbox(value=get_stats(), label="System Stats", interactive=False)
        refresh_btn = gr.Button("🔄 Refresh Stats", variant="secondary", size="sm")
    
    with gr.Tabs():
        with gr.Tab("Home & Database"):
            gr.Markdown("### ⚙️ Database Management")
            init_btn = gr.Button("🔨 Reinitialize Database with Sample Data", variant="stop")
            db_output = gr.Textbox(label="Database Status")
            init_btn.click(init_database, outputs=[db_output])
            
        with gr.Tab("Manage Courses"):
            gr.Markdown("### ➕ Add New Course")
            with gr.Row():
                c_code = gr.Textbox(label="Course Code (e.g., CSE101)")
                c_name = gr.Textbox(label="Course Name")
                c_branch = gr.Dropdown(choices=get_branches(), label="Branch")
            
            add_btn = gr.Button("Add Course", variant="primary")
            add_output = gr.Textbox(label="Status")
            
            add_btn.click(add_course, inputs=[c_code, c_name, c_branch], outputs=[add_output])
            
        with gr.Tab("Generate Timetable"):
            gr.Markdown("### 🧬 Genetic Algorithm Engine")
            gen_slider = gr.Slider(minimum=10, maximum=300, value=100, step=10, label="Generations (Complexity)")
            gen_btn = gr.Button("🚀 Start Generation Process", variant="primary")
            gen_status = gr.Textbox(label="Progress")
            gen_df = gr.DataFrame(label="Preview Result")
            
            gen_btn.click(generate_timetable, inputs=[gen_slider], outputs=[gen_df, gen_status])
            
        with gr.Tab("Final Timetable"):
            gr.Markdown("### 📋 View Generated Schedule")
            view_btn = gr.Button("📥 Fetch Current Timetable", variant="primary")
            view_df = gr.DataFrame(label="Current Schedule")
            
            view_btn.click(get_current_timetable, outputs=[view_df])

    refresh_btn.click(get_stats, outputs=[stats_box])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, theme=gr.themes.Soft())
