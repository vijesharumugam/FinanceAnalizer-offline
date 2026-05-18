"""Streamlit entrypoint for the AI Personal Finance Analyzer."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Dict, List

import pandas as pd
import streamlit as st

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
except ModuleNotFoundError:
    A4 = None
    getSampleStyleSheet = None
    Paragraph = None
    SimpleDocTemplate = None
    Spacer = None

from analytics.analysis import FinanceAnalyzer
from analytics.forecasting import ForecastService
from analytics.insights import InsightEngine
from auth.login import render_login_form
from auth.register import render_register_form
from auth.security import SecurityManager
from config import APP_NAME, EXPENSE_CATEGORIES, configure_logging, get_settings
from database.crud import FinanceCRUD
from database.db_connection import get_database_manager
from models.anomaly_detection import SpendingAnomalyDetector
from uploads.csv_handler import CSVExpenseParser
from visualization.charts import FinanceCharts

st.set_page_config(page_title=APP_NAME, page_icon="$", layout="wide", initial_sidebar_state="expanded")


def inject_css() -> None:
    """Apply a modern dashboard look using lightweight Streamlit CSS overrides."""

    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(19, 180, 158, 0.16), transparent 25%),
                radial-gradient(circle at bottom right, rgba(15, 76, 129, 0.14), transparent 22%),
                linear-gradient(135deg, #f5fbfb 0%, #eef4f6 100%);
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0d2f3f 0%, #12394a 100%);
        }
        [data-testid="stSidebar"] * {
            color: #f5fbfb;
        }
        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] textarea,
        [data-testid="stSidebar"] .stDateInput input,
        [data-testid="stSidebar"] [data-baseweb="input"] input,
        [data-testid="stSidebar"] [data-baseweb="select"] input,
        [data-testid="stSidebar"] [data-baseweb="select"] div {
            color: #0b1f2a !important;
            -webkit-text-fill-color: #0b1f2a !important;
        }
        [data-testid="stSidebar"] input::placeholder,
        [data-testid="stSidebar"] textarea::placeholder {
            color: #5c6f79 !important;
            -webkit-text-fill-color: #5c6f79 !important;
        }
        .finance-card {
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid rgba(13, 47, 63, 0.08);
            border-radius: 18px;
            padding: 1rem 1.1rem;
            box-shadow: 0 12px 30px rgba(18, 57, 74, 0.08);
            min-height: 120px;
        }
        .finance-card h4 {
            margin: 0;
            color: #40616f;
            font-size: 0.95rem;
        }
        .finance-card p {
            margin: 0.35rem 0 0 0;
            color: #0b1f2a;
            font-size: 1.6rem;
            font-weight: 700;
        }
        .insight-box {
            background: #ffffff;
            border-left: 5px solid #13b49e;
            border-radius: 14px;
            padding: 0.85rem 1rem;
            margin-bottom: 0.6rem;
            box-shadow: 0 10px 24px rgba(18, 57, 74, 0.06);
        }
        .feature-pill {
            display: inline-block;
            border-radius: 999px;
            background: #dff5ef;
            color: #0f5b50;
            padding: 0.35rem 0.75rem;
            margin: 0.15rem;
            font-size: 0.84rem;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource
def get_services():
    logger = configure_logging()
    crud = FinanceCRUD()
    services = {
        "logger": logger,
        "crud": crud,
        "security": SecurityManager(),
        "analyzer": FinanceAnalyzer(),
        "forecast": ForecastService(),
        "insights": InsightEngine(),
        "charts": FinanceCharts(),
        "parser": CSVExpenseParser(),
        "anomaly": SpendingAnomalyDetector(),
    }
    return services


def initialize_database() -> tuple[bool, str]:
    """Create the database and tables on first app load."""

    try:
        db_manager = get_database_manager()
        db_manager.initialize_schema()
        db_manager.test_connection()
        return True, "Database is connected and schema is ready."
    except Exception as exc:  # pragma: no cover - runtime environment dependent
        return False, f"MySQL initialization failed: {exc}"


def format_currency(value: float) -> str:
    return f"Rs. {value:,.2f}"


def render_kpi_cards(kpis) -> None:
    columns = st.columns(5)
    cards = [
        ("Total Spend", format_currency(kpis.total_spending)),
        ("This Month", format_currency(kpis.monthly_spending)),
        ("Avg Daily Spend", format_currency(kpis.average_daily_spend)),
        ("Savings %", f"{kpis.savings_percentage:.1f}%"),
        ("Budget Utilization", f"{kpis.budget_utilization:.1f}%"),
    ]
    for column, (label, value) in zip(columns, cards):
        column.markdown(f"<div class='finance-card'><h4>{label}</h4><p>{value}</p></div>", unsafe_allow_html=True)


def generate_pdf_summary(user: Dict, kpis, insights: List[str], monthly_df: pd.DataFrame) -> bytes:
    """Build a one-page PDF summary for download."""

    if SimpleDocTemplate is None or A4 is None or getSampleStyleSheet is None:
        raise RuntimeError("PDF export is unavailable because the 'reportlab' package is not installed.")

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(APP_NAME, styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"User: {user['full_name']} ({user['username']})", styles["BodyText"]),
        Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["BodyText"]),
        Spacer(1, 12),
        Paragraph(f"Total Spending: {format_currency(kpis.total_spending)}", styles["BodyText"]),
        Paragraph(f"Monthly Spending: {format_currency(kpis.monthly_spending)}", styles["BodyText"]),
        Paragraph(f"Savings Percentage: {kpis.savings_percentage:.1f}%", styles["BodyText"]),
        Spacer(1, 12),
        Paragraph("Savings Insights", styles["Heading2"]),
    ]
    for insight in insights:
        story.append(Paragraph(f"- {insight}", styles["BodyText"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Monthly Trend", styles["Heading2"]))
    for _, row in monthly_df.iterrows():
        story.append(Paragraph(f"{row['month']}: {format_currency(float(row['amount']))}", styles["BodyText"]))

    doc.build(story)
    return buffer.getvalue()


def render_setup_block(error_message: str) -> None:
    settings = get_settings()
    st.error(error_message)
    st.markdown("### MySQL setup required")
    st.code(
        "\n".join(
            [
                f"DB_HOST={settings.db_host}",
                f"DB_PORT={settings.db_port}",
                f"DB_USER={settings.db_user}",
                "DB_PASSWORD=your_mysql_password",
                f"DB_NAME={settings.db_name}",
            ]
        )
    )
    st.info("Create a `.env` file from `.env.example`, start MySQL, and reload the Streamlit app.")
    st.stop()


def render_auth_page(crud: FinanceCRUD, security_manager: SecurityManager) -> None:
    st.title(APP_NAME)
    st.caption("Track expenses, analyze behavior, predict future spending, and generate offline savings insights.")

    left, right = st.columns([1.3, 1], gap="large")
    with left:
        st.markdown(
            """
            <div class="finance-card">
                <h4>Production-ready starter</h4>
                <p style="font-size: 1rem; font-weight: 500; line-height: 1.6;">
                    Built with Streamlit, MySQL, Pandas, Scikit-learn, Plotly, secure authentication,
                    CSV ingestion, dashboards, anomaly detection, forecasts, and downloadable reports.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for label in [
            "Expense Tracking",
            "Budget Monitoring",
            "Interactive Charts",
            "ML Forecasting",
            "Smart Alerts",
            "CSV Uploads",
            "PDF Reporting",
            "Deployment Ready",
        ]:
            st.markdown(f"<span class='feature-pill'>{label}</span>", unsafe_allow_html=True)
    with right:
        login_tab, register_tab = st.tabs(["Login", "Register"])
        with login_tab:
            render_login_form(crud, security_manager)
        with register_tab:
            render_register_form(crud, security_manager)


def render_sidebar(user: Dict) -> Dict:
    st.sidebar.title("Finance Control Center")
    st.sidebar.write(f"Signed in as **{user['full_name']}**")
    page = st.sidebar.radio(
        "Navigation",
        [
            "Dashboard",
            "Expenses",
            "CSV Upload",
            "Budgets",
            "Predictions",
            "Alerts",
            "Reports",
            "Advanced Features",
        ],
    )
    st.sidebar.markdown("---")
    start_date = st.sidebar.date_input("Start Date", value=date.today() - timedelta(days=120))
    end_date = st.sidebar.date_input("End Date", value=date.today())
    if start_date > end_date:
        st.sidebar.warning("Start date cannot be after end date. The range has been corrected.")
        start_date, end_date = end_date, start_date
    category = st.sidebar.selectbox("Category Filter", ["All"] + EXPENSE_CATEGORIES)
    return {"page": page, "start_date": start_date, "end_date": end_date, "category": category}


def sync_smart_alerts(crud: FinanceCRUD, user_id: int, expenses_df: pd.DataFrame, budgets_df: pd.DataFrame, anomalies_df: pd.DataFrame) -> int:
    """Generate deduplicated alerts from budgets, anomalies, and trend spikes."""

    existing_alerts = crud.list_alerts(user_id, unresolved_only=True, limit=200)
    existing_messages = set(existing_alerts["message"].tolist()) if not existing_alerts.empty else set()
    created_count = 0

    if not budgets_df.empty and not expenses_df.empty:
        working_expenses = expenses_df.copy()
        working_expenses["txn_date"] = pd.to_datetime(working_expenses["txn_date"])
        current_month = working_expenses["txn_date"].max().to_period("M")
        current_month_df = working_expenses[working_expenses["txn_date"].dt.to_period("M") == current_month]
        working_budgets = budgets_df.copy()
        working_budgets["budget_month"] = pd.to_datetime(working_budgets["budget_month"])
        relevant_budgets = working_budgets[working_budgets["budget_month"].dt.to_period("M") == current_month]

        for _, budget in relevant_budgets.iterrows():
            if budget["category"] == "Overall":
                spent = float(current_month_df["amount"].sum())
            else:
                spent = float(current_month_df[current_month_df["category"] == budget["category"]]["amount"].sum())

            if spent > float(budget["amount"]):
                message = f"{budget['category']} budget exceeded by {spent - float(budget['amount']):,.2f}."
                if message not in existing_messages:
                    crud.create_alert(user_id, "budget_exceeded", "high", message)
                    existing_messages.add(message)
                    created_count += 1

    if not anomalies_df.empty:
        flagged_rows = anomalies_df[anomalies_df["is_anomaly"]].head(5)
        for _, row in flagged_rows.iterrows():
            message = f"Unusual transaction detected: {row['category']} spend of {float(row['amount']):,.2f} on {pd.to_datetime(row['txn_date']).date()}."
            if message not in existing_messages:
                crud.create_alert(user_id, "anomaly", "medium", message, int(row["id"]) if "id" in row else None)
                existing_messages.add(message)
                created_count += 1

    if not expenses_df.empty:
        trend_df = FinanceAnalyzer().monthly_comparison(expenses_df)
        if len(trend_df) >= 2:
            latest_change = float(trend_df.iloc[-1]["change_pct"])
            if latest_change > 20:
                message = f"Rapid spending growth detected: {latest_change:.1f}% month-over-month."
                if message not in existing_messages:
                    crud.create_alert(user_id, "spending_spike", "high", message)
                    created_count += 1

    return created_count


def render_dashboard(crud: FinanceCRUD, services: Dict, user: Dict, filters: Dict) -> None:
    analyzer = services["analyzer"]
    charts = services["charts"]
    insights_engine = services["insights"]
    anomaly_detector = services["anomaly"]

    expenses_df = crud.list_expenses(user["id"], filters["start_date"], filters["end_date"], filters["category"])
    all_expenses_df = crud.list_expenses(user["id"])
    budgets_df = crud.list_budgets(user["id"])
    kpis = analyzer.compute_kpis(expenses_df, budgets_df)

    st.title("Interactive Dashboard")
    render_kpi_cards(kpis)
    st.markdown("")

    monthly_df = analyzer.monthly_spending(expenses_df)
    category_df = analyzer.category_spending(expenses_df)
    daily_df = analyzer.daily_trend(expenses_df)
    comparison_df = analyzer.monthly_comparison(expenses_df)
    utilization_df = analyzer.budget_utilization(expenses_df, budgets_df)
    anomalies_df = anomaly_detector.detect(all_expenses_df)
    insights = insights_engine.generate_insights(expenses_df, budgets_df, anomalies_df=anomalies_df)

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.plotly_chart(charts.monthly_bar(monthly_df), use_container_width=True)
        st.plotly_chart(charts.daily_line(daily_df), use_container_width=True)
    with chart_col2:
        st.plotly_chart(charts.category_pie(category_df), use_container_width=True)
        st.plotly_chart(charts.monthly_comparison(comparison_df), use_container_width=True)

    lower_col1, lower_col2 = st.columns(2)
    with lower_col1:
        st.plotly_chart(charts.budget_utilization(utilization_df), use_container_width=True)
    with lower_col2:
        latest_alerts = crud.list_alerts(user["id"], unresolved_only=True, limit=5)
        st.subheader("Recent Alerts")
        if latest_alerts.empty:
            st.info("No unresolved alerts yet.")
        else:
            st.dataframe(latest_alerts, use_container_width=True, hide_index=True)

    st.subheader("Savings Insights")
    for insight in insights:
        st.markdown(f"<div class='insight-box'>{insight}</div>", unsafe_allow_html=True)

    if st.button("Refresh Smart Alerts", use_container_width=True):
        created_count = sync_smart_alerts(crud, user["id"], all_expenses_df, budgets_df, anomalies_df)
        st.success(f"{created_count} new alerts created.")
        st.rerun()


def render_expense_page(crud: FinanceCRUD, user: Dict) -> None:
    st.title("Expense Management")
    st.write("Add, edit, and remove transactions stored in MySQL.")

    with st.form("add_expense_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        txn_date = col1.date_input("Transaction Date", value=date.today())
        amount = col2.number_input("Amount", min_value=0.0, step=100.0)
        category = col3.selectbox("Category", EXPENSE_CATEGORIES)
        merchant = st.text_input("Merchant")
        description = st.text_area("Description")
        payment_method = st.selectbox("Payment Method", ["UPI", "Card", "Cash", "Net Banking", "Wallet", "Unknown"])
        submitted = st.form_submit_button("Add Expense", use_container_width=True)

    if submitted:
        if amount <= 0:
            st.error("Amount must be greater than 0.")
            return
        crud.add_expense(
            user["id"],
            {
                "txn_date": txn_date,
                "amount": amount,
                "category": category,
                "merchant": merchant,
                "description": description,
                "payment_method": payment_method,
                "source": "manual",
            },
        )
        st.success("Expense added successfully.")
        st.rerun()

    expenses_df = crud.list_expenses(user["id"])
    if expenses_df.empty:
        st.info("No expenses available. Add one above or upload a CSV.")
        return

    st.subheader("Recent Transactions")
    st.dataframe(expenses_df, use_container_width=True, hide_index=True)

    selectable_ids = expenses_df["id"].astype(int).tolist()
    selected_expense_id = st.selectbox("Select Expense ID to Edit/Delete", selectable_ids)
    selected_expense = crud.get_expense(int(selected_expense_id), user["id"])
    if not selected_expense:
        return

    widget_suffix = f"_{int(selected_expense_id)}"
    merchant_value = selected_expense["merchant"] if pd.notna(selected_expense["merchant"]) else ""
    description_value = selected_expense["description"] if pd.notna(selected_expense["description"]) else ""
    payment_options = ["UPI", "Card", "Cash", "Net Banking", "Wallet", "Unknown"]

    with st.expander("Edit Selected Expense"):
        with st.form(f"edit_expense_form{widget_suffix}"):
            col1, col2, col3 = st.columns(3)
            edit_date = col1.date_input(
                "Transaction Date",
                value=pd.to_datetime(selected_expense["txn_date"]).date(),
                key=f"edit_date{widget_suffix}",
            )
            edit_amount = col2.number_input(
                "Amount",
                min_value=0.0,
                value=float(selected_expense["amount"]),
                step=100.0,
                key=f"edit_amount{widget_suffix}",
            )
            edit_category = col3.selectbox(
                "Category",
                EXPENSE_CATEGORIES,
                index=EXPENSE_CATEGORIES.index(selected_expense["category"]) if selected_expense["category"] in EXPENSE_CATEGORIES else 0,
                key=f"edit_category{widget_suffix}",
            )
            edit_merchant = st.text_input("Merchant", value=merchant_value, key=f"edit_merchant{widget_suffix}")
            edit_description = st.text_area("Description", value=description_value, key=f"edit_description{widget_suffix}")
            edit_payment = st.selectbox(
                "Payment Method",
                payment_options,
                index=payment_options.index(selected_expense["payment_method"]) if selected_expense["payment_method"] in payment_options else 5,
                key=f"edit_payment{widget_suffix}",
            )
            updated = st.form_submit_button("Update Expense", use_container_width=True)

        if updated:
            if edit_amount <= 0:
                st.error("Amount must be greater than 0.")
                return
            crud.update_expense(
                int(selected_expense_id),
                user["id"],
                {
                    "txn_date": edit_date,
                    "amount": edit_amount,
                    "category": edit_category,
                    "merchant": edit_merchant,
                    "description": edit_description,
                    "payment_method": edit_payment,
                    "source": selected_expense["source"],
                },
            )
            st.success("Expense updated.")
            st.rerun()

    if st.button("Delete Selected Expense", type="secondary", use_container_width=True):
        crud.delete_expense(int(selected_expense_id), user["id"])
        st.warning("Expense deleted.")
        st.rerun()


def render_csv_upload_page(crud: FinanceCRUD, parser: CSVExpenseParser, user: Dict) -> None:
    st.title("CSV Statement Upload")
    st.write("Upload bank statements and map them into normalized expense records.")
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded_file is None:
        st.info("Use `data/sample_expenses.csv` if you want a quick starter dataset.")
        return

    parse_result = parser.parse(uploaded_file)
    for warning_message in parse_result.warnings:
        st.warning(warning_message)

    cleaned_df = parse_result.cleaned_data
    st.subheader("Parsed Preview")
    st.dataframe(cleaned_df, use_container_width=True, hide_index=True)

    if cleaned_df.empty:
        return

    if st.button("Import to MySQL", use_container_width=True):
        imported_rows = crud.bulk_insert_expenses(user["id"], cleaned_df)
        st.success(f"{imported_rows} expense rows imported successfully.")
        st.rerun()


def render_budget_page(crud: FinanceCRUD, services: Dict, user: Dict) -> None:
    st.title("Budget Tracking")
    with st.form("budget_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        budget_month = col1.date_input("Budget Month", value=date.today().replace(day=1))
        category = col2.selectbox("Budget Category", ["Overall"] + EXPENSE_CATEGORIES)
        amount = col3.number_input("Budget Amount", min_value=0.0, step=500.0)
        submitted = st.form_submit_button("Save Budget", use_container_width=True)

    if submitted:
        normalized_month = budget_month.replace(day=1)
        if amount <= 0:
            st.error("Budget amount must be greater than 0.")
            return
        crud.set_budget(user["id"], normalized_month, category, amount)
        st.success("Budget saved.")
        st.rerun()

    budgets_df = crud.list_budgets(user["id"])
    st.subheader("Configured Budgets")
    st.dataframe(budgets_df, use_container_width=True, hide_index=True)

    expenses_df = crud.list_expenses(user["id"])
    utilization_df = services["analyzer"].budget_utilization(expenses_df, budgets_df)
    if not utilization_df.empty:
        st.plotly_chart(services["charts"].budget_utilization(utilization_df), use_container_width=True)


def render_prediction_page(crud: FinanceCRUD, services: Dict, user: Dict) -> None:
    st.title("Machine Learning Predictions")
    expenses_df = crud.list_expenses(user["id"])
    if expenses_df.empty:
        st.info("Add at least a few months of expenses to train the prediction models.")
        return

    if st.button("Train Models and Forecast", use_container_width=True):
        result = services["forecast"].generate_forecast(expenses_df, periods=3)
        st.session_state["latest_forecast"] = result

        next_month = (pd.to_datetime(expenses_df["txn_date"]).max().to_period("M") + 1).to_timestamp().date()
        crud.create_prediction(
            user_id=user["id"],
            prediction_month=next_month,
            model_name=result["selected_model"],
            predicted_amount=result["next_month_prediction"],
            confidence_score=result["confidence_score"],
            mae=result["mae"],
            rmse=result["rmse"],
            metadata={"metrics": result["metrics"]},
        )

    result = st.session_state.get("latest_forecast") or services["forecast"].generate_forecast(expenses_df, periods=3)
    st.subheader("Model Summary")
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Selected Model", result["selected_model"])
    metric_col2.metric("Next Month Forecast", format_currency(result["next_month_prediction"]))
    metric_col3.metric("Confidence", f"{result['confidence_score']:.1f}%")

    metrics_df = pd.DataFrame(result["metrics"])
    if not metrics_df.empty:
        st.dataframe(metrics_df, use_container_width=True, hide_index=True)

    st.plotly_chart(services["charts"].forecast_chart(result["history_df"], result["forecast_df"]), use_container_width=True)

    anomalies_df = services["anomaly"].detect(expenses_df)
    st.plotly_chart(services["charts"].anomaly_scatter(anomalies_df), use_container_width=True)
    st.subheader("Stored Prediction History")
    st.dataframe(crud.list_predictions(user["id"]), use_container_width=True, hide_index=True)


def render_alert_page(crud: FinanceCRUD, user: Dict) -> None:
    st.title("Smart Alert System")
    unresolved_only = st.toggle("Show unresolved alerts only", value=True)
    alerts_df = crud.list_alerts(user["id"], unresolved_only=unresolved_only)
    if alerts_df.empty:
        st.info("No alerts available.")
        return

    st.dataframe(alerts_df, use_container_width=True, hide_index=True)
    if "is_resolved" not in alerts_df.columns or "id" not in alerts_df.columns:
        st.warning("Alert data is missing required columns.")
        return

    unresolved_alerts = alerts_df if unresolved_only else alerts_df.loc[~alerts_df["is_resolved"].fillna(False)]
    alert_ids = unresolved_alerts["id"].dropna().astype(int).tolist()
    if not alert_ids:
        return

    alert_id = st.selectbox("Resolve Alert ID", alert_ids)
    if st.button("Mark Alert as Resolved", use_container_width=True):
        crud.resolve_alert(int(alert_id), user["id"])
        st.success("Alert resolved.")
        st.rerun()


def render_report_page(crud: FinanceCRUD, services: Dict, user: Dict, filters: Dict) -> None:
    st.title("Export Reports")
    expenses_df = crud.list_expenses(user["id"], filters["start_date"], filters["end_date"], filters["category"])
    budgets_df = crud.list_budgets(user["id"])
    kpis = services["analyzer"].compute_kpis(expenses_df, budgets_df)
    insights = services["insights"].generate_insights(expenses_df, budgets_df)
    monthly_df = services["analyzer"].monthly_spending(expenses_df)

    st.dataframe(expenses_df, use_container_width=True, hide_index=True)
    csv_bytes = expenses_df.to_csv(index=False).encode("utf-8")

    st.download_button("Download CSV Report", data=csv_bytes, file_name="finance_report.csv", mime="text/csv", use_container_width=True)
    if SimpleDocTemplate is None:
        st.warning("PDF export is unavailable because `reportlab` is not installed in the Python environment running Streamlit.")
    else:
        pdf_bytes = generate_pdf_summary(user, kpis, insights, monthly_df)
        st.download_button("Download PDF Summary", data=pdf_bytes, file_name="finance_summary.pdf", mime="application/pdf", use_container_width=True)


def render_advanced_features() -> None:
    st.title("Advanced Offline Features")
    st.markdown(
        """
        ### Roadmap-ready local modules
        - OCR receipt scanning: connect Tesseract or PaddleOCR locally for image-to-expense extraction.
        - Voice expense logging: add an offline speech-to-text layer such as Vosk or faster-whisper.
        - Offline assistant: build a local rules engine or connect a fully local model runtime later if needed.
        - Multi-user support: already supported at the database and authentication layer.
        - Local deployment: run directly with Streamlit or use Docker Compose on the same machine.
        """
    )


def main() -> None:
    inject_css()
    services = get_services()
    db_ready, db_message = initialize_database()
    if not db_ready:
        render_setup_block(db_message)

    security_manager = services["security"]
    crud = services["crud"]
    if not security_manager.is_authenticated():
        render_auth_page(crud, security_manager)
        return

    user = security_manager.get_current_user()
    filters = render_sidebar(user)
    if st.sidebar.button("Logout", use_container_width=True):
        security_manager.logout_user()
        st.rerun()

    page = filters["page"]
    if page == "Dashboard":
        render_dashboard(crud, services, user, filters)
    elif page == "Expenses":
        render_expense_page(crud, user)
    elif page == "CSV Upload":
        render_csv_upload_page(crud, services["parser"], user)
    elif page == "Budgets":
        render_budget_page(crud, services, user)
    elif page == "Predictions":
        render_prediction_page(crud, services, user)
    elif page == "Alerts":
        render_alert_page(crud, user)
    elif page == "Reports":
        render_report_page(crud, services, user, filters)
    elif page == "Advanced Features":
        render_advanced_features()


if __name__ == "__main__":
    main()
