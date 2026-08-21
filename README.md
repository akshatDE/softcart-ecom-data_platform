<div align="center">

# 👋 Hi, I'm Akshat Sharma

### Data Engineer × AI Developer

<img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=600&size=22&duration=3000&pause=900&color=00D9FF&center=true&vCenter=true&width=850&lines=Building+Scalable+Data+Platforms;Engineering+Production+ETL+%26+ELT+Pipelines;Exploring+AI+%2B+Data+Infrastructure;Building+with+Spark+%7C+Airflow+%7C+BigQuery+%7C+LLMs" alt="Typing SVG" />

<br/>

<a href="https://akshatde-portfolio.base44.app/">
  <img src="https://img.shields.io/badge/Portfolio-Visit-00D9FF?style=for-the-badge&logo=googlechrome&logoColor=white" />
</a>
<a href="https://www.linkedin.com/in/akshat-sharma-35a514222">
  <img src="https://img.shields.io/badge/LinkedIn-Connect-0077B5?style=for-the-badge&logo=linkedin&logoColor=white" />
</a>
<a href="mailto:sharmaakshat0001@gmail.com">
  <img src="https://img.shields.io/badge/Email-Contact_Me-EA4335?style=for-the-badge&logo=gmail&logoColor=white" />
</a>

</div>

---

## 🚀 About Me

I build data platforms, ETL/ELT pipelines, analytical systems, and AI-powered data applications.

Three years of production data engineering taught me the unglamorous parts — reconciliation, quality gates, failure triage, the schema conversation you have six months before anyone notices you were right. That's the foundation. AI is the layer I'm building on top of it: RAG, local LLMs, Text-to-SQL, tool-calling agents.

Most teams bolt AI onto their stack after the fact. I'd rather design for it from the start.

**🔍 Open to Data Engineering and AI-integrated data roles.**

---

## 🛠️ Tech Stack

<div align="center">

**Languages**

<img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/SQL-336791?style=for-the-badge&logo=postgresql&logoColor=white" />
<img src="https://img.shields.io/badge/Bash-4EAA25?style=for-the-badge&logo=gnubash&logoColor=white" />

**Data Engineering & Orchestration**

<img src="https://img.shields.io/badge/Apache%20Airflow-017CEE?style=for-the-badge&logo=apacheairflow&logoColor=white" />
<img src="https://img.shields.io/badge/Apache%20Spark%20(PySpark)-E25A1C?style=for-the-badge&logo=apachespark&logoColor=white" />
<img src="https://img.shields.io/badge/Databricks-FF3621?style=for-the-badge&logo=databricks&logoColor=white" />
<img src="https://img.shields.io/badge/pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white" />

<sub>ETL/ELT · Dimensional (Kimball) Modeling · Medallion Architecture · Data Quality · Distributed & Batch Processing</sub>

**Databases & Warehouses**

<img src="https://img.shields.io/badge/BigQuery-669DF6?style=for-the-badge&logo=googlebigquery&logoColor=white" />
<img src="https://img.shields.io/badge/Snowflake-29B5E8?style=for-the-badge&logo=snowflake&logoColor=white" />
<img src="https://img.shields.io/badge/DuckDB-FFF000?style=for-the-badge&logo=duckdb&logoColor=black" />
<img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" />
<img src="https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white" />
<img src="https://img.shields.io/badge/MongoDB-47A248?style=for-the-badge&logo=mongodb&logoColor=white" />

**Cloud**

<img src="https://img.shields.io/badge/AWS-232F3E?style=for-the-badge&logo=amazonaws&logoColor=white" />
<img src="https://img.shields.io/badge/Google%20Cloud-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white" />

<sub>S3 · Glue · Lambda · Athena · Step Functions · EventBridge · SNS · CloudWatch · EC2</sub>

**AI / LLM Engineering**

<img src="https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logo=ollama&logoColor=white" />
<img src="https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white" />
<img src="https://img.shields.io/badge/LangGraph-111111?style=for-the-badge" />
<img src="https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white" />

<sub>RAG · Text-to-SQL · Tool-Calling Agents · Local Inference · Prompt & Context Engineering</sub>

**Backend & DevOps**

<img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
<img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" />
<img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
<img src="https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white" />
<img src="https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black" />

</div>

---

## 🏗️ Featured Engineering Projects

### 🛒 SoftCart — E-commerce Data Platform + AI

`Airflow` `DuckDB` `PostgreSQL` `MySQL` `MongoDB` `FastAPI` `Ollama` `Docker`

End-to-end analytics platform pairing a conventional warehouse architecture with local LLM-powered Text-to-SQL.

<a href="https://github.com/akshatDE/softcart-ecom-data_platform">
  <img src="https://raw.githubusercontent.com/akshatDE/softcart-ecom-data_platform/main/softcart-ecom.png" alt="SoftCart architecture" width="100%" />
</a>

- 2 fact tables at order-item grain, 7 conformed dimensions with surrogate keys
- Two blocking DQ gates backed by a pytest suite that fails the run on violation
- SQL safety validator: SELECT-only, keyword denylist, table allowlist, injected LIMIT, read-only connection
- Docker Compose cut contributor setup from ~2 hours to under 10 minutes

<a href="https://github.com/akshatDE/softcart-ecom-data_platform">
  <img src="https://img.shields.io/badge/View_Project-181717?style=for-the-badge&logo=github&logoColor=white" />
</a>

---

### 📺 YT Trending Data Pipeline — Cloud-Native Analytics Platform

`AWS` `PySpark` `Glue` `S3` `Athena` `Step Functions` `Lambda` `QuickSight`

Cloud-native pipeline ingesting and transforming YouTube trending data across 10 regions.

<a href="https://github.com/akshatDE/YT-Trending-Data-Pipeline">
  <img src="https://raw.githubusercontent.com/akshatDE/YT-Trending-Data-Pipeline/main/dashboard/infra-screenshots/YT-TrendingPipeline.png" alt="YouTube trending pipeline architecture" width="100%" />
</a>

- Bronze–Silver–Gold medallion on Snappy Parquet with Hive-style region partitioning, provisioned via Boto3
- Quality gates at two boundaries: row-count floors, null thresholds, schema conformance, 48-hour freshness
- Step Functions on a 6-hour EventBridge schedule with exponential-backoff retries and SNS alerts
- QuickSight dashboard over four Athena SPICE datasets

<a href="https://github.com/akshatDE/YT-Trending-Data-Pipeline">
  <img src="https://img.shields.io/badge/View_Project-181717?style=for-the-badge&logo=github&logoColor=white" />
</a>

---

### 🤖 Pure Python Local Agent — AI Agent From Scratch

`Python` `Ollama` `Groq` `FastAPI` `Streamlit`

A tool-calling agent built without LangChain or any agent framework — the loop written by hand to understand what the framework abstracts away.

<a href="https://github.com/akshatDE/AgenticAILearning/tree/main/pure-python-local-agent">
  <img src="https://raw.githubusercontent.com/akshatDE/AgenticAILearning/main/pure-python-local-agent/python_agent_arch.png" alt="Pure Python agent architecture" width="100%" />
</a>

- JSON tool schemas and a name-to-function registry
- Bounded loop appending results to conversation memory, exiting on a toolless answer
- Four tools against live REST APIs: weather, currency, arithmetic, web search
- Two interchangeable backends: local Qwen 9B offline, hosted Groq for the demo

<a href="https://github.com/akshatDE/AgenticAILearning/tree/main/pure-python-local-agent">
  <img src="https://img.shields.io/badge/View_Project-181717?style=for-the-badge&logo=github&logoColor=white" />
</a>

---

## 🎯 Engineering Philosophy

**Build the fundamentals first. Add abstractions when they solve a real problem.**

Understanding the layer underneath the framework is what makes the framework useful — which is why I keep rebuilding things from their primitives before reaching for the library that hides them.

<pre>
     DATA ENGINEERING
            │
   ┌────────┼────────┐
   ▼        ▼        ▼
Python     SQL     Spark
   │        │        │
   └────────┼────────┘
            ▼
  Distributed Systems
            ▼
      System Design
            ▼
     AI ENGINEERING
            │
   ┌────────┼────────┐
   ▼        ▼        ▼
  RAG    Agents    LLMs
   │        │        │
   └────────┼────────┘
            ▼
    AI + Data Systems
</pre>

**Currently going deeper on:** Spark internals, agentic AI, context engineering, and production AI infrastructure.

---

## 💼 Engineering Experience

**Data Engineer** — Neel Data Pro IT Solutions · Jul 2021 – Jul 2024

- 🔄 Integrated 6+ heterogeneous source systems into a centralized BigQuery warehouse
- 🗃️ Migrated 10M+ records off legacy systems, reconciling row counts to confirm zero loss at cutover
- 📦 Processed ~2.5 GB of daily tourism data
- ⚡ Cut report generation from ~4 hours to 30 minutes for 15+ government stakeholders
- 🛡️ Implemented validation at load boundaries: row counts, null thresholds, schema conformance, referential integrity
- 📈 Built 8+ Tableau dashboards tracking segment KPIs, informing 4 strategic funding decisions
- 📚 Authored pipeline runbooks and a warehouse data dictionary so analysts could self-serve

---

## 🎓 Education & Certifications

<table>
<tr>
<td width="50%" valign="top">

### 🎓 M.S. Business Analytics

**University of Massachusetts Boston**
*Major: AI & Data Analytics* · 2024 — 2026

**GPA: 4.0 / 4.0**

Advanced AI/ML · Applied AI · Big Data Processing · Data Warehousing

</td>
<td width="50%" valign="top">

### 💻 B.Tech Computer Science

**Chitkara University**
2019 — 2023

**GPA: 3.74 / 4.0**

Programming · Algorithms · Databases · Software Engineering

</td>
</tr>
</table>

<div align="center">

<img src="https://img.shields.io/badge/IBM-Data%20Engineering%20Professional-052FAD?style=for-the-badge&logo=ibm&logoColor=white" />
<img src="https://img.shields.io/badge/Snowflake-University%20Platform%20Skills-29B5E8?style=for-the-badge&logo=snowflake&logoColor=white" />
<img src="https://img.shields.io/badge/Hugging%20Face-AI%20Agents%20Fundamentals-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black" />

</div>

---

<div align="center">

**Building reliable data systems that power intelligent applications.**

<a href="https://github.com/akshatDE">
  <img src="https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white" />
</a>

</div>
