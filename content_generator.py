# content_generator.py
# Local-dev friendly content generator for LinkedIn posts.
# - DEV_MODE=1 (default): No external API calls, no SMTP. Generates realistic mock posts.
# - DEV_MODE=0: Uses Perplexity API (if PERPLEXITY_API_KEY is set) + optional SMTP digest.

import os
import re
import json
import time
import random
from datetime import datetime, timezone
from urllib.parse import urlparse

# Optional deps (prod mode)
try:
    import requests
    import smtplib
    from email.mime.text import MIMEText
    from email.utils import formatdate
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class ContentGenerator:
    """
    Generates LinkedIn-ready posts with:
    - Clean text (no JSON, no bracketed citations, no Markdown bold/italics/code fences)
    - Source URL appended at the end of post content
    - Image URL when available
    Dev mode (default): offline, deterministic, no network.
    Prod mode: calls Perplexity API and (optionally) emails a review digest.
    """

    PPLX_URL = "https://api.perplexity.ai/chat/completions"

    # DEV_MODE=1 means dev mode enabled; DEV_MODE=0 means prod/API mode
    DEV_MODE = os.getenv("DEV_MODE", "0") in ("1", "true", "True")

    TOPIC_PILLARS = [
        "EV traction inverter design: SiC vs GaN trade-offs for 800V",
        "FOC control intuition for IPMSM: d-q axes and torque ripple",
        "On-board charger topologies (totem-pole PFC) and EMI pitfalls",
        "Thermal paths in power modules: junction→case→sink (ΔT & lifetime)",
        "Battery BMS basics: SOC vs SOH estimation and calibration drift",
        "Zonal E/E architectures: impact on harness, latency, diagnostics",
        "HIL workflows for traction control: SIL→HIL→dyno validation funnel",
        "DC-DC converter magnetics in EVs: core selection and ripple",
        "V2G/V2H engineer's view: control stability and grid codes",
        "Regenerative braking blend: safety, pedal feel, and controls",
    ]

    TRUSTED_DOMAINS = {
        "ieee.org", "ieeexplore.ieee.org", "sae.org", "nrel.gov", "energy.gov",
        "iea.org", "iso.org", "iec.ch", "arxiv.org", "nature.com",
        "sciencedirect.com", "springer.com", "cell.com", "charin.global",
        "infineon.com", "onsemi.com", "st.com", "ti.com", "microchip.com",
        "navitassemi.com", "wolfspeed.com", "semiengineering.com",
        "insideevs.com", "electrive.com", "greencarcongress.com",
        "reuters.com", "bloomberg.com", "techcrunch.com", "electrek.co",
        "greencarreports.com", "caranddriver.com", "motortrend.com",
        "mathworks.com", "ni.com", "dspace.com",
    }

    STYLE_GUIDE = (
        "Voice: clear, structured, systems-level engineer. Prefer short paragraphs or "
        "tight bullet points. Focus on architecture, control, and practical trade-offs. "
        "Avoid marketing fluff. Be precise, but conversational. 150–220 words. "
        "Use 3–6 relevant hashtags. 0–2 well-chosen emojis max. End with a thoughtful question. "
        "ABSOLUTELY NO bracketed numeric citations like [1], [2] or (1). No 'References' blocks. "
        "If you cite, write nothing in-text—only produce a single final 'source_url' field."
    )

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY")

        # Email config (only used in prod)
        self.email_host = os.getenv("EMAIL_HOST", "smtp.gmail.com")
        self.email_port = int(os.getenv("EMAIL_PORT", "587"))
        self.email_user = os.getenv("EMAIL_USER")
        self.email_pass = os.getenv("EMAIL_PASS")
        self.email_from = os.getenv("EMAIL_FROM")
        self.email_to = os.getenv("EMAIL_TO")

        # Network defaults (prod only)
        self.req_timeout = (12, 18)  # (connect, read)
        self.max_retries = 2

    # ---------------- Public API ----------------
    def generate_posts(self):
        """
        Returns a list of dicts:
        {
            "title": str,
            "content": str,            # Clean post text with 'Source: …' footer
            "created_at": datetime UTC,
            "source_url": str|None,    # Stored separately too
            "batch_timestamp": datetime UTC,
            "image_url": str|None
        }
        """
        batch_time = datetime.now(timezone.utc)
        topics = self._weekly_topics(batch_time)
        results = []

        for topic in topics:
            if self.DEV_MODE or not self.api_key or not HAS_REQUESTS:
                content, url, image_url = self._mock_post(topic, batch_time)
            else:
                content, url, image_url = self._api_post(topic)

            if not content:
                continue

            # Clean content
            content = self._ensure_clean_content(content)

            # Guarantee source URL
            if not url:
                url = self._get_fallback_source(topic)

            # Append a neat source footer to the content
            content = self._append_source_footer(content, url)

            results.append({
                "title": topic,
                "content": content,
                "created_at": datetime.now(timezone.utc),
                "source_url": url,
                "batch_timestamp": batch_time,
                "image_url": image_url,
            })

            time.sleep(0.1 if self.DEV_MODE else 0.8)

        return results

    # ---------------- Topic rotation ----------------
    def _weekly_topics(self, batch_time):
        """Return 4 topics for this week, deterministically."""
        week_seed = batch_time.isocalendar()[1]
        random.seed(week_seed)
        shuffled = self.TOPIC_PILLARS[:]
        random.shuffle(shuffled)
        return shuffled[:4]

    # ---------------- Dev content ----------------
    def _mock_post(self, topic, batch_time):
        """Generate realistic mock content (with image and source) for development."""
        week_seed = batch_time.isocalendar()[1]
        topic_hash = hash(topic) % 1000
        random.seed(week_seed + topic_hash)

        content = (
            f"Recent breakthroughs in {topic.lower()} are transforming EV power systems engineering.\n\n"
            "Key technical advances:\n"
            "• Improved efficiency by 15–20% through optimized switching strategies\n"
            "• Enhanced thermal management reducing junction temperatures\n"
            "• Better EMI compliance with advanced filtering techniques\n"
            "• Streamlined validation workflows accelerating time-to-market\n\n"
            "The engineering challenge lies in balancing performance, cost, and reliability "
            "while meeting stringent automotive requirements. System-level integration is critical for SOP.\n\n"
            "What optimization strategies have proven most effective in your power electronics projects? ⚙️\n\n"
            "#PowerElectronics #EVEngineering #Inverters #BMS"
        )

        # Credible source
        domains = list(self.TRUSTED_DOMAINS)
        random.shuffle(domains)
        source_url = f"<https://{domains>[0]}/research/technical-article/{random.randint(1000, 9999)}"

        # Include image often in dev for UI validation
        image_url = f"https://picsum.photos/seed/{random.randint(1, 9999)}/900/450" if random.random() > 0.3 else None

        return content, source_url, image_url

    # ---------------- API content ----------------
    def _api_post(self, topic):
        """Call Perplexity API and return clean content, credible source, and image URL."""
        try:
            system_prompt = (
                "You are a professional technical writer for LinkedIn posts on EV and power electronics.\n"
                "Write a single LinkedIn-ready post (150–200 words), technical but conversational, "
                "include 3–5 relevant hashtags, up to 2 emojis, and end with a question.\n"
                "CRITICAL: Do not use Markdown styling (no bold/italics/headers), no bracketed citations like [1], [2], "
                "and no 'Source:' line in the content. Return the post as plain text only."
            )
            user_prompt = f"Topic: {topic}. Focus on recent developments, practical engineering insights, and trade-offs."

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            data = {
                "model": "sonar",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 700,
                "return_citations": True,
                "return_images": True,
            }

            r = requests.post(self.PPLX_URL, headers=headers, json=data, timeout=self.req_timeout)
            r.raise_for_status()
            resp = r.json()

            # Extract text
            raw = resp.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
            content = raw.strip()

            # Extract credible source from citations (handle dicts and strings)
            source_url = None
            for cit in (resp.get("citations") or []):
                url = cit["url"] if isinstance(cit, dict) else str(cit)
                if self._is_credible_source(url):
                    source_url = url
                    break

            # Extract first image URL if present
            image_url = None
            for img in (resp.get("images") or []):
                if isinstance(img, dict):
                    image_url = img.get("image_url") or img.get("url")
                    if image_url:
                        break
                elif isinstance(img, str):
                    image_url = img
                    break

            # Fallback if API produced nothing useful
            if not content:
                return self._mock_post(topic, datetime.now(timezone.utc))

            return content, source_url, image_url

        except Exception as e:
            print(f"Error calling Perplexity API: {e}")
            return self._mock_post(topic, datetime.now(timezone.utc))

    # ---------------- Cleaning & formatting ----------------
    def _ensure_clean_content(self, content: str) -> str:
        """Ensure content is plain text (no JSON blocks) and fully cleaned."""
        if not content:
            return ""

        t = content.strip()

        # If fenced `````` block
        fenced = re.search(r"``````", t, re.IGNORECASE)
        if fenced:
            t = fenced.group(1).strip()

        # If content looks like JSON, try parsing for 'post'/'content' fields
        if t.startswith("{") and t.endswith("}"):
            try:
                data = json.loads(t)
                for key in ("post", "content", "text", "body"):
                    if isinstance(data.get(key), str) and len(data[key]) > 20:
                        t = data[key]
                        break
            except json.JSONDecodeError:
                pass

        return self._clean_content(t)

    def _clean_content(self, content: str) -> str:
        """Remove citations, links in body, and Markdown markers; normalize whitespace."""
        if not content:
            return ""

        # Remove bracketed and numeric citations
        content = re.sub(r"\[\d+\]", "", content)
        content = re.sub(r"\(\d+\)", "", content)

        # Remove 'Source:' lines and inline URLs
        content = re.sub(r"(?i)\bSource\s*:\s*https?://\S+", "", content)
        content = re.sub(r"https?://\S+", "", content)

        # Remove JSON-like key-value fragments that sometimes leak
        content = re.sub(r'"[^"]*":\s*"[^"]*"', "", content)
        content = re.sub(r"\{[^}]*\}", "", content)

        # Decode common escapes
        content = content.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")

        # Strip Markdown bold/italics/code fences
        content = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", content)   # **bold**, *italic*, ***both***
        content = re.sub(r"`{1,3}([^`]+)`{1,3}", r"\1", content)     # `code` or ``````
        content = re.sub(r"```", "", content)                        # block fence end

        # Optional: normalize bullets
        content = content.replace("•", "- ")

        # Normalize whitespace and add paragraph breaks after periods
        content = " ".join(content.split())
        content = re.sub(r"\.\s+", ".\n\n", content)

        return content.strip()

    def _append_source_footer(self, content: str, source_url: str | None) -> str:
        """Append a neat 'Source: …' line to the end of the post content."""
        if not source_url:
            return content
        if "Source:" in content:
            return content
        return content.rstrip() + f"\n\nSource: {source_url}"

    # ---------------- Credibility helpers ----------------
    def _is_credible_source(self, url: str | None) -> bool:
        if not url:
            return False
        try:
            domain = urlparse(url).netloc.lower().replace("www.", "")
            return any(trusted in domain for trusted in self.TRUSTED_DOMAINS)
        except Exception:
            return False

    def _get_fallback_source(self, topic: str) -> str:
        t = topic.lower()
        if any(k in t for k in ("battery", "bms", "charging", "energy", "v2g")):
            return "https://www.energy.gov/eere/vehicles/electric-vehicle-research"
        if any(k in t for k in ("inverter", "converter", "sic", "gan", "power", "thermal", "junction")):
            return "https://ieeexplore.ieee.org/browse/periodicals/title/transactions"
        if any(k in t for k in ("foc", "ipmsm", "motor", "control", "hil")):
            return "https://www.mathworks.com/solutions/power-electronics-control.html"
        return "https://www.sae.org/news/mobility-engineering"

    # ---------------- Email digest (optional) ----------------
    def build_email_digest(self, posts):
        dt = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        subject = f"LinkedIn posts ready for review — {dt}"

        html_lines = ["<h2>Weekly LinkedIn Posts</h2>"]
        text_lines = ["Weekly LinkedIn Posts\n" + "=" * 20]

        for i, p in enumerate(posts, 1):
            html_lines.append(f"<h3>Post {i}: {self._esc(p.get('title',''))}</h3>")
            html_lines.append(f"<p>{self._esc(p.get('content',''))}</p>")
            if p.get("source_url"):
                html_lines.append(f'<p><a href="{p["source_url"]}">Source</a></p>')

            text_lines.extend([
                f"\nPost {i}: {p.get('title','')}",
                "-" * 40,
                p.get('content',''),
                f"Source: {p.get('source_url', 'N/A')}\n",
            ])

        return subject, "\n".join(html_lines), "\n".join(text_lines)

    def send_email_digest(self, posts):
        if self.DEV_MODE:
            subject, html_body, text_body = self.build_email_digest(posts)
            with open("email_preview.html", "w") as f:
                f.write(f"<title>{subject}</title>\n{html_body}")
            with open("email_preview.txt", "w") as f:
                f.write(f"Subject: {subject}\n\n{text_body}")
            print("Email preview saved to email_preview.html and email_preview.txt")
            return True

        if not all([self.email_host, self.email_user, self.email_pass, self.email_to]) or not HAS_REQUESTS:
            print("Email configuration incomplete or SMTP not available; skipping email")
            return False

        try:
            subject, html_body, _ = self.build_email_digest(posts)
            msg = MIMEText(html_body, "html")
            msg["Subject"] = subject
            msg["From"] = self.email_from or self.email_user
            msg["To"] = self.email_to
            msg["Date"] = formatdate(localtime=True)

            with smtplib.SMTP(self.email_host, self.email_port) as server:
                server.starttls()
                server.login(self.email_user, self.email_pass)
                server.send_message(msg)

            print(f"Email digest sent successfully to {self.email_to}")
            return True
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False

    def _esc(self, text: str | None) -> str:
        if not text:
            return ""
        return (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#x27;")
        )
