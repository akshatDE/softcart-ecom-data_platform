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


</div>
