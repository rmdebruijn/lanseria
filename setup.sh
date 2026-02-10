#!/bin/bash
BASE='/home/rutger/Documents/NexusNovus/Projects/4. Raising'
MODEL="$BASE/bLAN_sWTP_NWL_no8433/11. Financial Model/model"
ln -s "$BASE/bLAN_sWTP_NWL_no8433" "$BASE/bLAN_sWTP_NWL_#8433"
rm -f "$MODEL/config/research_data.json"
cd "$MODEL" && venv/bin/python scripts/create_intelligence_db.py && venv/bin/streamlit run app.py --server.port 8501
