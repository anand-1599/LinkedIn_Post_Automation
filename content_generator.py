# content_generator.py
# Production content generator for LinkedIn posts using Perplexity API

import os
import re
import json
import time
import random
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests
import smtplib
from email.mime.text import MIMEText
from email.utils import formatdate


class ContentGenerator:
    """
    Generates LinkedIn-ready posts with:
    - Clean text (no JSON, no bracketed citations, no Markdown bold/italics/code fences)
    - Source URL appended at the end of post content
    - Image URL when available
    Production mode: calls Perplexity API and (optionally) emails a review digest.
    """

    PPLX_URL = "https://api.perplexity.ai/chat/completions"

    TOPIC_PILLARS = [
        "EV traction inverter design: SiC vs GaN trade-offs for 800V systems",
        "FOC control strategies for IPMSM: d-q axes optimization and torque ripple reduction",
        "On-board charger topologies: totem-pole PFC design and EMI mitigation",
        "Thermal management in power modules: junction-to-case thermal paths and lifetime impact",
        "Battery BMS architecture: SOC vs SOH estimation algorithms and calibration drift",
        "Zonal E/E architectures in EVs: impact on harness complexity and diagnostic capabilities", 
        "HIL validation workflows for traction control: SIL to HIL to dyno testing pipeline",
        "DC-DC converter magnetics design: core material selection and ripple optimization",
        "V2G/V2H control systems: grid stability considerations and safety protocols",
        "Regenerative braking control algorithms: safety blending and pedal feel optimization",
        "Wide-bandgap semiconductors in automotive: SiC MOSFET vs GaN switching performance",
        "Motor control advances: sensorless FOC implementations and position estimation",
        "Fast charging infrastructure: CCS vs CHAdeMO protocols and power delivery optimization",
        "Battery thermal management systems: liquid cooling vs air cooling trade-offs",
        "Power electronics packaging: wire bonding vs copper clip technologies",
        "EV powertrain integration: mechanical and electrical interface design challenges",
        "Battery second-life applications: grid storage systems and capacity degradation models",
        "Electric vehicle platform architectures: skateboard vs integrated design approaches",
        "Power semiconductor reliability: MTBF analysis and failure mode prediction",
        "EV charging network interoperability: roaming protocols and payment systems"
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
        "mathworks.com", "ni.com", "dspace.com", "powerelectronics.com",
        # Global OEM official sites
        "tesla.com", "bmw.com", "mercedes-benz.com", "audi.com", "ford.com",
        "gm.com", "hyundai.com", "toyota.com", "byd.com", "nio.com",
        "rivian.com", "lucidmotors.com", "porsche.com", "stellantis.com",
        "volkswagen.com", "volvo.com", "polestar.com", "fisker.com",
        # Indian OEMs and brands
        "tatamotors.com", "tata.com", "mahindra.com", "mahindraauto.com",
        "royalenfield.com", "bajaj.com", "bajajauto.com", "heromotocorp.com",
        "tvsmotor.com", "maruti.co.in", "suzuki.co.in", "hyundai.co.in",
        "mahindraelectric.com", "olaelectric.com", "atherenergy.com",
        "simpleenergy.in", "ultraviolette.com", "riverindiaelectric.com",
        "mahindralastmile.com", "mahindrarise.com", "tatanexon.com",
        "nexonev.tatamotors.com", "tigorev.tatamotors.com",
        # Indian auto industry forums and news
        "autocarindia.com", "autocarpro.in", "rushlane.com", "gaadiwaadi.com",
        "cardekho.com", "carwale.com", "zigwheels.com", "carandbike.com",
        "team-bhp.com", "autocar.co.uk/india", "motorindiaonline.in",
        "expressauto.in", "financialexpress.com", "business-standard.com",
        "livemint.com", "economictimes.indiatimes.com", "moneycontrol.com",
        # Indian technology and industry forums
        "siam.in", "acmainfo.com", "siamindia.com", "cii.in", "ficci.in",
        "assocham.org", "nasscom.in", "electronics.gov.in", "dst.gov.in",
        "niti.gov.in", "investindia.gov.in", "makeinindia.com",
        "electricvehicles.in", "evreporter.com", "evtales.com",
        "cleantechnica.com/india", "inc42.com", "yourstory.com",
        # Indian research institutions
        "iitb.ac.in", "iitd.ac.in", "iitm.ac.in", "iitk.ac.in", "iisc.ac.in",
        "isro.gov.in", "drdo.gov.in", "csir.res.in", "nplindia.org",
        # Industry news
        "autonews.com", "automotive-news.com", "wardsauto.com",
        "teslarati.com", "cleantechnica.com", "electriveco.com"
    }

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY")
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY is required for production mode")

        # Email config (optional)
        self.email_host = os.getenv("EMAIL_HOST", "smtp.gmail.com")
        self.email_port = int(os.getenv("EMAIL_PORT", "587"))
        self.email_user = os.getenv("EMAIL_USER")
        self.email_pass = os.getenv("EMAIL_PASS")
        self.email_from = os.getenv("EMAIL_FROM")
        self.email_to = os.getenv("EMAIL_TO")

        # Network defaults
        self.req_timeout = (12, 18)  # (connect, read)
        self.max_retries = 2

    def generate_posts(self, existing_posts=None):
        """
        Generate posts with deduplication check.
        existing_posts: list of recent posts to check against for duplicates
        """
        existing_posts = existing_posts or []
        batch_time = datetime.now(timezone.utc)
        topics = self._weekly_topics(batch_time)
        results = []
        max_retries = 3

        for topic in topics:
            retry_count = 0
            
            while retry_count < max_retries:
                content, url, image_url = self._api_post(topic)

                if not content:
                    retry_count += 1
                    continue

                # Clean content
                content = self._ensure_clean_content(content)
                
                # Check for duplicates
                temp_post = {"content": content}
                if not self._is_duplicate_content(content, existing_posts + results):
                    # Guarantee source URL
                    if not url:
                        url = self._get_fallback_source(topic)

                    # Append source footer
                    content = self._append_source_footer(content, url)

                    results.append({
                        "title": topic,
                        "content": content,
                        "created_at": datetime.now(timezone.utc),
                        "source_url": url,
                        "batch_timestamp": batch_time,
                        "image_url": image_url,
                    })
                    break
                else:
                    print(f"Duplicate content detected for topic: {topic[:50]}...")
                    retry_count += 1

                time.sleep(0.8)

        return results

    def _weekly_topics(self, batch_time):
        """Return mix of trending news + core topics for this week."""
        # Get fresh trending topics
        trending = self._get_trending_topics()
        
        # Get deterministic core topics
        week_seed = batch_time.isocalendar()[1]
        random.seed(week_seed)
        shuffled_core = self.TOPIC_PILLARS[:]
        random.shuffle(shuffled_core)
        
        # Mix: 3 trending + 2 core topics (or 4 core if no trending)
        if trending:
            final_topics = trending[:3] + shuffled_core[:2]
        else:
            final_topics = shuffled_core[:5]
        
        return final_topics[:5]

    def _api_post(self, topic):
        """Call Perplexity API and return clean content, credible source, and image URL."""
        try:
            system_prompt = (
                "You are Anand Golla, a Master's student in Power Engineering at TUM with experience "
                "in EV powertrain development at Royal Enfield. Write a professional LinkedIn post "
                "about power electronics and EV technology. Use a technical but conversational tone, "
                "include practical engineering insights, and structure content with clear points. "
                "150-220 words. Include 3-5 relevant hashtags and end with a thoughtful question. "
                "Use 0-2 emojis maximum. CRITICAL: No bracketed citations [1], [2] or (1). "
                "No markdown formatting (**bold**, *italic*). Return plain text only."
            )
            user_prompt = (
                f"Topic: {topic}. Focus on recent technical developments, practical trade-offs, "
                "and engineering challenges. Include system-level considerations and real-world applications."
            )

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

            # Extract credible source from citations
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

            return content, source_url, image_url

        except Exception as e:
            print(f"Error calling Perplexity API: {e}")
            return None, None, None

    def _ensure_clean_content(self, content: str) -> str:
        """Ensure content is plain text (no JSON blocks) and fully cleaned."""
        if not content:
            return ""

        t = content.strip()

        # If fenced code block
        fenced = re.search(r"```(?:\w+)?\n(.*?)\n```", t, re.DOTALL)
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
        content = re.sub(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]", "", content)
        content = re.sub(r"\(\s*\d+\s*\)", "", content)

        # Remove 'Source:' lines and inline URLs
        content = re.sub(r"(?i)\bSource\s*:\s*https?://\S+", "", content)
        content = re.sub(r"https?://\S+", "", content)

        # Remove JSON-like key-value fragments that sometimes leak
        content = re.sub(r'"[^"]*":\s*"[^"]*"', "", content)
        content = re.sub(r"\{[^}]*\}", "", content)

        # Decode common escapes
        content = content.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")

        # Strip Markdown formatting
        content = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", content)   # **bold**, *italic*
        content = re.sub(r"`{1,3}([^`]+)`{1,3}", r"\1", content)     # `code`
        content = re.sub(r"```", "", content)                        # code fences

        # Normalize whitespace
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = re.sub(r'[ \t]{2,}', ' ', content)

        return content.strip()

    def _append_source_footer(self, content: str, source_url: str | None) -> str:
        """Append a neat 'Source: …' line to the end of the post content."""
        if not source_url:
            return content
        if "Source:" in content:
            return content
        return content.rstrip() + f"\n\nSource: {source_url}"

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
        if any(k in t for k in ("inverter", "converter", "sic", "gan", "power", "thermal")):
            return "https://ieeexplore.ieee.org/browse/periodicals/title/transactions"
        if any(k in t for k in ("foc", "ipmsm", "motor", "control", "hil")):
            return "https://www.mathworks.com/solutions/power-electronics-control.html"
        return "https://www.sae.org/news/mobility-engineering"

    def build_email_digest(self, posts):
        """Build email digest for post review."""
        dt = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        subject = f"LinkedIn posts ready for review — {dt}"

        html_lines = [
            "<h2>Weekly LinkedIn Posts</h2>",
            '<p><strong>Check your posts here:</strong> <a href="https://linkedin-post-automation-10tf.onrender.com/">https://linkedin-post-automation-10tf.onrender.com/</a></p>',
            "<hr>"
        ]
        text_lines = [
            "Weekly LinkedIn Posts\n" + "=" * 20,
            "",
            "Check your posts here: https://linkedin-post-automation-10tf.onrender.com/",
            "-" * 60,
            ""
        ]

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
        """Send email digest if configured."""
        if not all([self.email_host, self.email_user, self.email_pass, self.email_to]):
            print("Email configuration incomplete; skipping email")
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
        """HTML escape helper."""
        if not text:
            return ""
        return (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#x27;")
        )

    def _get_trending_topics(self):
        """Get trending EV news topics from Perplexity API."""
        try:
            system_prompt = (
                "You are a technology research assistant. Provide 5 current trending topics "
                "in electric vehicles and power electronics from the past 2 weeks. Focus on "
                "OEM announcements, new technologies, partnerships, and industry developments. "
                "Return ONLY topic titles, one per line, no numbering or bullets."
            )
            user_prompt = (
                "What are the latest trending news and innovations in the EV industry from "
                "major OEMs like Tesla, BMW, Mercedes, Audi, Ford, GM, Hyundai, Toyota, "
                "BYD, NIO, Rivian, Lucid? Include power electronics, battery tech, charging "
                "infrastructure, and autonomous driving developments from the past 2 weeks."
            )

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
                "temperature": 0.3,  # Lower temperature for more focused results
                "max_tokens": 400,
                "return_citations": True,
            }

            r = requests.post(self.PPLX_URL, headers=headers, json=data, timeout=self.req_timeout)
            r.raise_for_status()
            resp = r.json()

            content = resp.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
            
            # Parse topics from response
            topics = []
            for line in content.strip().split('\n'):
                line = line.strip()
                if line and len(line) > 10:  # Filter out short/empty lines
                    # Clean up any numbering or bullets
                    line = re.sub(r'^\d+\.?\s*', '', line)
                    line = re.sub(r'^[-•*]\s*', '', line)
                    topics.append(line)
            
            return topics[:5]  # Return max 5 topics
            
        except Exception as e:
            print(f"Error getting trending topics: {e}")
            return []

    def _is_duplicate_content(self, new_content: str, existing_posts: list) -> bool:
        """Check if content is too similar to existing posts."""
        import difflib
        
        new_words = set(new_content.lower().split())
        
        for existing in existing_posts:
            existing_words = set(existing.get('content', '').lower().split())
            
            # Calculate similarity ratio
            similarity = len(new_words & existing_words) / len(new_words | existing_words)
            
            if similarity > 0.7:  # 70% similarity threshold
                return True
        
        return False
