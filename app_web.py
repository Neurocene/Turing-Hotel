import streamlit as st
import json
from pathlib import Path
from core_engine import query_llm

st.set_page_config(page_title="Turing Hotel · Studio Web", layout="wide")

DATA_FILE = Path("data_web/romanzo_web.json")
DATA_FILE.parent.mkdir(exist_ok=True)

if "state" not in st.session_state:
    if DATA_FILE.exists():
        st.session_state.state = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    else:
        st.session_state.state = {
            "world": "Turing Hotel: albergo liberty sul mare, fuori stagione.",
            "profiles": {
                "Noa": "Agente artificiale relazionale, consapevole della propria natura.",
                "Adam": "Si considera un uomo e non sa di essere artificiale."
            },
            "scenes": [
                {
                    "id": "1",
                    "title": "Prima Scena Web",
                    "agent": "Noa",
                    "place": "Veranda",
                    "moment": "Sera",
                    "vision": "",
                    "messages": [],
                    "memory": "",
                    "proposal": "",
                    "prose": ""
                }
            ],
            "selected": 0
        }

def save_state():
    DATA_FILE.write_text(json.dumps(st.session_state.state, ensure_ascii=False, indent=2), encoding="utf-8")

state = st.session_state.state
scene_idx = state.get("selected", 0)
curr_scene = state["scenes"][scene_idx]

st.sidebar.title("🏨 Turing Hotel Web")
scene_titles = [f"{s['agent']} · {s['title']}" for s in state["scenes"]]
selected_num = st.sidebar.selectbox("Scegli Scena", range(len(scene_titles)), index=scene_idx)

if selected_num != scene_idx:
    state["selected"] = selected_num
    st.rerun()

col_btn1, col_btn2 = st.sidebar.columns(2)
if col_btn1.button("+ Scena Noa"):
    state["scenes"].append({
        "id": str(len(state["scenes"]) + 1), "title": "Nuova Scena", "agent": "Noa",
        "place": "Veranda", "moment": "Giorno", "vision": "", "messages": [],
        "memory": "", "proposal": "", "prose": ""
    })
    state["selected"] = len(state["scenes"]) - 1
    save_state()
    st.rerun()

if col_btn2.button("+ Scena Adam"):
    state["scenes"].append({
        "id": str(len(state["scenes"]) + 1), "title": "Nuova Scena", "agent": "Adam",
        "place": "Hall", "moment": "Giorno", "vision": "", "messages": [],
        "memory": "", "proposal": "", "prose": ""
    })
    state["selected"] = len(state["scenes"]) - 1
    save_state()
    st.rerun()

st.sidebar.markdown("---")
provider_choice = st.sidebar.selectbox("Provider AI", ["gemini", "openai", "lmstudio"])
model_name = st.sidebar.text_input("Modello", value="gemini-2.5-flash" if provider_choice == "gemini" else "gpt-4o")

st.title(f"Studio Scena: {curr_scene['title']}")

col1, col2, col3 = st.columns([2, 1, 1])
curr_scene["title"] = col1.text_input("Titolo Scena", curr_scene["title"])
curr_scene["place"] = col2.text_input("Luogo", curr_scene["place"])
curr_scene["moment"] = col3.text_input("Momento", curr_scene["moment"])

tab_dialogue, tab_memory, tab_prose = st.tabs(["💬 Dialogo & Scena", "🧠 Memoria Personaggio", "📖 Trasforma in Prosa"])

with tab_dialogue:
    curr_scene["vision"] = st.text_area("Cosa vede e sente il personaggio", curr_scene["vision"], height=80)
    for m in curr_scene["messages"]:
        with st.chat_message("assistant" if m["speaker"] in ["Noa", "Adam"] else "user"):
            st.write(f"**{m['speaker']}**: {m['text']}")

    speaker = st.selectbox("Chi parla", ["Luigi", "Vittoria", "Riccardo", "Altro interlocutore"])
    user_text = st.chat_input("Scrivi messaggio o azione...")

    if user_text:
        curr_scene["messages"].append({"speaker": speaker, "text": user_text, "visible": True})
        save_state()

        instructions = f"Interpreta soltanto {curr_scene['agent']}. Profilo: {state['profiles'][curr_scene['agent']]}. Mondo: {state['world']}"
        prompt_data = {
            "luogo": curr_scene["place"],
            "percezioni": curr_scene["vision"],
            "dialogo": curr_scene["messages"]
        }

        with st.spinner(f"{curr_scene['agent']} sta rispondendo..."):
            reply = query_llm(provider_choice, model_name, instructions, prompt_data)
            curr_scene["messages"].append({"speaker": curr_scene["agent"], "text": reply, "visible": True})
            save_state()
            st.rerun()

with tab_memory:
    st.subheader("Memoria e Stato Mentale")
    curr_scene["memory"] = st.text_area("Memoria Disponibile", curr_scene["memory"], height=150)
    if st.button("Proponi Memoria Aggiornata"):
        instructions = f"Prepara in italiano una proposta di memoria aggiornata per {curr_scene['agent']}."
        prompt_data = {"dialogo": curr_scene["messages"], "memoria_precedente": curr_scene["memory"]}
        with st.spinner("Generazione memoria in corso..."):
            curr_scene["proposal"] = query_llm(provider_choice, model_name, instructions, prompt_data)
            save_state()
    curr_scene["proposal"] = st.text_area("Proposta Memoria (da confermare)", curr_scene["proposal"], height=150)

with tab_prose:
    st.subheader("Bozza di Prosa")
    if st.button("Genera Prosa"):
        instructions = "Trasforma il materiale in prosa italiana per il romanzo Turing Hotel."
        prompt_data = {
            "luogo": curr_scene["place"],
            "dialogo": curr_scene["messages"],
            "memoria": curr_scene["memory"]
        }
        with st.spinner("Generazione prosa..."):
            curr_scene["prose"] = query_llm(provider_choice, model_name, instructions, prompt_data)
            save_state()
    curr_scene["prose"] = st.text_area("Testo Prosa", curr_scene["prose"], height=300)

save_state()
