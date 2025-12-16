"""AI Sentiment Analyzer (Streamlit)

Created by Ishan Chakraborty
License: MIT
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Dict, Tuple

import streamlit as st

try:
    from openai import OpenAI, APIConnectionError, APIError, AuthenticationError, RateLimitError, OpenAIError
except Exception:
    OpenAI = None  # type: ignore
    APIConnectionError = APIError = AuthenticationError = RateLimitError = OpenAIError = Exception  # type: ignore


APP_TITLE = "AI Sentiment Analyzer"
DEFAULT_MODEL = "gpt-4o"

RECOMMENDED_MODELS = [
    ("gpt-5", "Next-gen flagship model"),
    ("gpt-5-mini", "GPT-5 optimized for speed"),
    ("gpt-4.1", "Best quality, reasoning, safer"),
    ("gpt-4.1-mini", "Balanced quality/speed"),
    ("gpt-4o", "Strong vision + reasoning"),
    ("gpt-4o-mini", "Fast + cost-efficient"),
]

SENTIMENT_LABELS = ["Positive", "Negative", "Neutral", "Mixed"]

EXAMPLES: Dict[str, str] = {
    "Positive": "I'm genuinely impressed by how quickly the team resolved my issue. The support agent was patient, clear, and followed up to ensure everything worked.",
    "Negative": "I'm frustrated because the delivery was two days late and the package arrived damaged. Customer support kept me waiting and didn't provide a clear resolution.",
    "Neutral": "The meeting is scheduled for 3 PM tomorrow. Please share the updated agenda and the final slide deck when you can.",
    "Mixed": "The product quality is excellent and the design looks premium, but the setup process was confusing and the instructions were missing key steps.",
}


@dataclass
class SentimentResult:
    sentiment: str
    confidence: float
    explanation: str
    key_phrases: list[str]


def _looks_like_openai_key(key: str) -> bool:
    key = key.strip()
    return bool(re.match(r"^(sk-|sess-|rk-).+", key)) or len(key) >= 20 if key else False


def _get_client(api_key: str) -> "OpenAI":
    if OpenAI is None:
        raise RuntimeError("openai package is not installed")
    return OpenAI(api_key=api_key)


def validate_api_key(api_key: str) -> Tuple[bool, str]:
    if not _looks_like_openai_key(api_key):
        return False, "Key format looks incorrect."
    try:
        client = _get_client(api_key)
        _ = client.models.list()
        return True, "Key validated successfully."
    except AuthenticationError:
        return False, "Authentication failed: invalid or revoked API key."
    except RateLimitError:
        return True, "Key is valid, but you are rate-limited right now."
    except APIConnectionError:
        return False, "Could not reach OpenAI (network/connectivity issue)."
    except APIError as e:
        return False, f"OpenAI API error while validating key: {getattr(e, 'message', str(e))}"
    except OpenAIError as e:
        return False, f"OpenAI error while validating key: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error while validating key: {str(e)}"


def analyze_sentiment(*, client: "OpenAI", model: str, text: str) -> tuple[SentimentResult, str]:
    system = "You are a careful sentiment analysis assistant. Classify sentiment for the user's text into exactly one of: Positive, Negative, Neutral, Mixed. Return strict JSON only (no markdown)."
    schema = {
        "sentiment": "Positive|Negative|Neutral|Mixed",
        "confidence": "number between 0 and 1",
        "explanation": "short explanation (1-3 sentences)",
        "key_phrases": "array of 3-8 short phrases from the input that justify the sentiment",
    }
    user = f"Analyze the sentiment of the following text and return JSON with keys exactly as in this schema: {json.dumps(schema)}\n\nText: {text}"
    
    # Configure parameters based on model type
    # GPT-5 and reasoning models require temperature=1 (or default)
    is_reasoning_model = model.lower().startswith('gpt-5') or 'reasoning' in model.lower()
    
    if is_reasoning_model:
        # GPT-5 models only support temperature=1 (default)
        resp = client.chat.completions.create(
            model=model, 
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=1
        )
    else:
        # Standard models support temperature=0 for deterministic output
        resp = client.chat.completions.create(
            model=model, 
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0
        )
    
    # Extract reasoning for reasoning models (GPT-5, etc.)
    reasoning = ""
    if hasattr(resp.choices[0].message, 'reasoning_content') and resp.choices[0].message.reasoning_content:
        reasoning = resp.choices[0].message.reasoning_content
    
    content = (resp.choices[0].message.content or "").strip()
    
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Model did not return JSON.")
        data = json.loads(content[start : end + 1])
    
    sentiment = str(data.get("sentiment", "")).strip()
    if sentiment not in SENTIMENT_LABELS:
        raise ValueError(f"Unexpected sentiment label: {sentiment}")
    
    confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
    explanation = str(data.get("explanation", "")).strip()
    key_phrases = data.get("key_phrases", [])
    if not isinstance(key_phrases, list):
        key_phrases = []
    key_phrases = [str(x).strip() for x in key_phrases if str(x).strip()][:12]
    
    return SentimentResult(sentiment=sentiment, confidence=confidence, explanation=explanation, key_phrases=key_phrases), reasoning


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🧠", layout="wide", initial_sidebar_state="expanded")

    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        * {font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;}
        .block-container {padding-top: 2rem; padding-bottom: 3rem;}
        .hero-container {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 20px; padding: 2.5rem 2rem; margin-bottom: 2.5rem; box-shadow: 0 10px 40px rgba(102, 126, 234, 0.2); color: white;}
        .hero-title {font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem; color: white;}
        .hero-subtitle {font-size: 1.1rem; color: rgba(255,255,255,0.9); margin-bottom: 1.5rem; line-height: 1.6;}
        .hero-grid {display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-top: 1.5rem;}
        .stat-card {background: rgba(255,255,255,0.15); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.2); border-radius: 12px; padding: 1rem 1.2rem; transition: transform 0.2s;}
        .stat-card:hover {transform: translateY(-2px);}
        .stat-icon {font-size: 1.5rem; margin-bottom: 0.3rem;}
        .stat-label {font-size: 0.85rem; opacity: 0.9; margin-bottom: 0.2rem;}
        .stat-value {font-size: 0.95rem; font-weight: 600;}
        .feature-pills {margin-top: 1.2rem;}
        .pill {display: inline-flex; align-items: center; gap: 0.4rem; background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); color: white; border-radius: 999px; padding: 0.4rem 1rem; font-size: 0.9rem; margin-right: 0.5rem; margin-bottom: 0.5rem; font-weight: 500;}
        .process-flow {display: flex; gap: 1rem; margin-top: 1.5rem; flex-wrap: wrap;}
        .process-step {flex: 1; min-width: 200px; background: rgba(255,255,255,0.15); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.2); border-radius: 12px; padding: 1rem; display: flex; align-items: center; gap: 0.8rem;}
        .step-icon {width: 40px; height: 40px; background: rgba(255,255,255,0.25); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.3rem; flex-shrink: 0;}
        .step-content {flex: 1;}
        .step-title {font-weight: 600; font-size: 0.95rem; margin-bottom: 0.15rem;}
        .step-desc {font-size: 0.85rem; opacity: 0.9;}
        .section-header {display: flex; align-items: center; gap: 0.6rem; margin: 2rem 0 1rem 0; padding-bottom: 0.7rem; border-bottom: 2px solid #e5e7eb;}
        .section-icon {font-size: 1.5rem;}
        .section-title {font-size: 1.4rem; font-weight: 700; color: #1f2937; margin: 0;}
        .stButton button {border-radius: 12px; border: 2px solid #e5e7eb; font-weight: 500; transition: all 0.2s;}
        .stButton button:hover {border-color: #667eea; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);}
        .info-card {background: #ffffff; border: 1px solid #e5e7eb; border-radius: 16px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.04); margin: 1rem 0;}
        .footer {text-align: center; padding: 2rem 0 1rem 0; color: #6b7280; font-size: 0.9rem; border-top: 1px solid #e5e7eb; margin-top: 3rem;}
        .footer-badge {display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 0.3rem 0.8rem; border-radius: 999px; font-size: 0.85rem; font-weight: 600; margin: 0 0.3rem;}
        </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
        <div class="hero-container">
            <div class="hero-title">🧠 {APP_TITLE}</div>
            <div class="hero-subtitle">Advanced LLM-powered sentiment classification system providing instant, accurate analysis of text sentiment with detailed explanations and confidence metrics.</div>
            <div class="feature-pills">
                <span class="pill">🧠 OpenAI GPT-4 Models</span>
                <span class="pill">🔐 Secure Key Validation</span>
                <span class="pill">⚡ Real-time Analysis</span>
                <span class="pill">📊 Confidence Metrics</span>
            </div>
            <div class="process-flow">
                <div class="process-step"><div class="step-icon">🔑</div><div class="step-content"><div class="step-title">Step 1: Authenticate</div><div class="step-desc">Validate your OpenAI API key</div></div></div>
                <div class="process-step"><div class="step-icon">✍️</div><div class="step-content"><div class="step-title">Step 2: Input Text</div><div class="step-desc">Paste text for analysis</div></div></div>
                <div class="process-step"><div class="step-icon">🤖</div><div class="step-content"><div class="step-title">Step 3: Analyze</div><div class="step-desc">Get sentiment classification</div></div></div>
            </div>
            <div class="hero-grid">
                <div class="stat-card"><div class="stat-icon">😊 😐 😞 😕</div><div class="stat-label">Sentiment Types</div><div class="stat-value">Positive · Negative · Neutral · Mixed</div></div>
                <div class="stat-card"><div class="stat-icon">🎯</div><div class="stat-label">Analysis Output</div><div class="stat-value">Label · Confidence · Explanation</div></div>
                <div class="stat-card"><div class="stat-icon">🚀</div><div class="stat-label">Available Models</div><div class="stat-value">GPT-5 · GPT-4.1 · 4o · 4o-mini</div></div>
                <div class="stat-card"><div class="stat-icon">✨</div><div class="stat-label">Key Features</div><div class="stat-value">JSON Output · Key Phrases</div></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if "api_key" not in st.session_state:
        st.session_state.api_key = ""
    if "key_valid" not in st.session_state:
        st.session_state.key_valid = False
    if "key_status" not in st.session_state:
        st.session_state.key_status = ""
    if "input_text" not in st.session_state:
        st.session_state.input_text = ""

    with st.sidebar:
        st.markdown("""
            <div style="text-align: center; padding: 1rem 0 1.5rem 0; border-bottom: 2px solid #e5e7eb; margin-bottom: 1.5rem;">
                <div style="font-size: 3rem; margin-bottom: 0.5rem;">🧠</div>
                <div style="font-size: 1.2rem; font-weight: 700; color: #1f2937; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">{}</div>
                <div style="font-size: 0.8rem; color: #6b7280; margin-top: 0.3rem;">AI-Powered Analysis</div>
            </div>
        """.format(APP_TITLE), unsafe_allow_html=True)
        
        st.header("⚙️ Setup")
        st.write("**Step 1:** Enter and validate your OpenAI API key.")
        api_key = st.text_input("OpenAI API Key", type="password", value=st.session_state.api_key, placeholder="sk-...", help="Your key is used only to call OpenAI from this app session.")

        col_a, col_b = st.columns([1, 1])
        with col_a:
            validate_clicked = st.button("Validate Key", use_container_width=True)
        with col_b:
            clear_clicked = st.button("Clear", use_container_width=True)

        if clear_clicked:
            st.session_state.api_key = ""
            st.session_state.key_valid = False
            st.session_state.key_status = ""
            st.rerun()

        if api_key != st.session_state.api_key:
            st.session_state.api_key = api_key
            st.session_state.key_valid = False
            st.session_state.key_status = ""

        if validate_clicked:
            if not api_key.strip():
                st.session_state.key_valid = False
                st.session_state.key_status = "Please enter an API key."
            else:
                ok, msg = validate_api_key(api_key)
                st.session_state.key_valid = ok
                st.session_state.key_status = msg

        if st.session_state.key_status:
            (st.success if st.session_state.key_valid else st.error)(st.session_state.key_status)

        st.divider()
        st.header("🤖 Model")

        option_labels = [f"{mid} — {note}" for mid, note in RECOMMENDED_MODELS]
        default_idx = next((idx for idx, (mid, _) in enumerate(RECOMMENDED_MODELS) if mid == DEFAULT_MODEL), 0)
        selected_label = st.selectbox("Recommended models", options=option_labels, index=default_idx, help="Pick a recommended model for sentiment analysis.")
        model = selected_label.split(" — ", 1)[0]

        st.divider()
        st.caption("Created by Ishan Chakraborty • MIT License")

    st.markdown('<div class="section-header"><span class="section-icon">✍️</span><h2 class="section-title">Input Text for Analysis</h2></div>', unsafe_allow_html=True)
    st.markdown("Choose from curated examples or paste your own text for sentiment classification.")

    sentiment_icons = {"Positive": "😊", "Negative": "😞", "Neutral": "😐", "Mixed": "😕"}
    example_cols = st.columns(4)
    for idx, label in enumerate(SENTIMENT_LABELS):
        with example_cols[idx]:
            if st.button(f"{sentiment_icons[label]} {label} Example", use_container_width=True, key=f"ex_{label}"):
                st.session_state.input_text = EXAMPLES[label]

    st.text_area("📝 Text to analyze", key="input_text", height=180, placeholder="Type or paste any text here (reviews, emails, feedback, social media posts, etc.)...", help="Enter text between 10-2000 characters for best results")

    with st.expander("📚 View Example Sentiments", expanded=False):
        st.markdown("##### Professional examples for each sentiment category")
        for label in SENTIMENT_LABELS:
            st.markdown(f"**{sentiment_icons[label]} {label}**")
            st.info(EXAMPLES[label])

    st.markdown('<div class="section-header"><span class="section-icon">🤖</span><h2 class="section-title">Run Analysis</h2></div>', unsafe_allow_html=True)

    analyze_disabled = not st.session_state.key_valid
    col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 3])
    with col_btn1:
        analyze_btn = st.button("🚀 Analyze Sentiment", type="primary", use_container_width=True, disabled=analyze_disabled, help=("⚠️ Validate your OpenAI API key first in the sidebar" if analyze_disabled else "Click to run sentiment analysis using the selected OpenAI model"))
    
    if analyze_disabled:
        st.warning("⚠️ Please validate your OpenAI API key in the sidebar before analyzing.")

    if analyze_btn:
        text = (st.session_state.input_text or "").strip()
        if not text:
            st.error("❌ Please enter some text to analyze.")
        elif len(text) < 10:
            st.error("❌ Text is too short. Please enter at least 10 characters.")
        else:
            # Check if reasoning model
            is_reasoning_model = model.lower().startswith('gpt-5') or 'reasoning' in model.lower()
            spinner_msg = f"🧠 {model} is thinking and reasoning..." if is_reasoning_model else "🤖 Analyzing sentiment with AI..."
            
            with st.spinner(spinner_msg):
                try:
                    client = _get_client(st.session_state.api_key)
                    result, reasoning = analyze_sentiment(client=client, model=model, text=text)
                    
                    # Display reasoning steps if available (for reasoning models)
                    if reasoning:
                        with st.expander("🧠 View Model Reasoning Process", expanded=False):
                            st.markdown("##### Internal Thinking Steps")
                            st.info(reasoning)
                            st.caption(f"This shows how {model} reasoned through the sentiment analysis task.")

                    st.markdown('<div class="section-header"><span class="section-icon">📊</span><h2 class="section-title">Analysis Results</h2></div>', unsafe_allow_html=True)
                    
                    sentiment_colors = {"Positive": "#10b981", "Negative": "#ef4444", "Neutral": "#6b7280", "Mixed": "#f59e0b"}
                    color = sentiment_colors.get(result.sentiment, "#6b7280")
                    emoji = sentiment_icons[result.sentiment]
                    confidence_pct = int(result.confidence * 100)
                    
                    st.markdown(f"""
                        <div class="info-card" style="border-left: 4px solid {color};">
                            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 1rem;">
                                <div>
                                    <div style="font-size: 0.85rem; color: #6b7280; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.3rem;">Detected Sentiment</div>
                                    <div style="font-size: 2rem; font-weight: 700; color: {color}; display: flex; align-items: center; gap: 0.5rem;"><span>{emoji}</span><span>{result.sentiment}</span></div>
                                </div>
                                <div style="text-align: right;">
                                    <div style="font-size: 0.85rem; color: #6b7280; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.3rem;">Confidence</div>
                                    <div style="font-size: 2rem; font-weight: 700; color: {color};">{confidence_pct}%</div>
                                </div>
                            </div>
                            <div style="background: #f9fafb; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
                                <div style="font-size: 0.9rem; color: #374151; line-height: 1.6;"><strong style="color: #1f2937;">💡 Explanation:</strong> {result.explanation}</div>
                            </div>
                    """, unsafe_allow_html=True)
                    
                    if result.key_phrases:
                        phrases_html = "".join([f'<span style="display: inline-block; background: {color}20; color: {color}; padding: 0.35rem 0.75rem; border-radius: 999px; margin: 0.25rem; font-size: 0.9rem; font-weight: 500; border: 1px solid {color}40;">{phrase}</span>' for phrase in result.key_phrases])
                        st.markdown(f'<div style="margin-top: 1rem;"><div style="font-size: 0.9rem; color: #374151; font-weight: 600; margin-bottom: 0.5rem;">🔑 Key Phrases:</div><div>{phrases_html}</div></div></div>', unsafe_allow_html=True)
                    else:
                        st.markdown("</div>", unsafe_allow_html=True)

                    st.success("✅ Analysis completed successfully!")
                    st.info("💡 **Pro Tip:** For better accuracy, provide context about who wrote the text, what situation it describes, and any relevant background information.")

                except AuthenticationError:
                    st.session_state.key_valid = False
                    st.error("🔐 Authentication failed: Your API key was rejected. Please validate a new key in the sidebar.")
                except RateLimitError:
                    st.error("⏱️ Rate limit reached. Please wait a moment before trying again.")
                except APIConnectionError:
                    st.error("🌐 Network error: Could not connect to OpenAI. Please check your internet connection.")
                except APIError as e:
                    st.error(f"❌ OpenAI API error: {getattr(e, 'message', str(e))}")
                except Exception as e:
                    st.error(f"❌ Unexpected error: {str(e)}")

    st.markdown("""
        <div class="footer">
            <div style="margin-bottom: 1rem;">
                <span class="footer-badge">Created by Ishan Chakraborty</span>
                <span class="footer-badge">MIT License</span>
            </div>
            <div style="color: #9ca3af; font-size: 0.85rem;">
                🔒 Privacy: Your API key and text are used only for analysis during this session. No data is stored or shared.<br/>
                ⚠️ Do not paste sensitive or confidential information.
            </div>
        </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
