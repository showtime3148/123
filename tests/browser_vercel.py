"""Optional integration check: real browser OCR with ASGI responses, no live API key."""
import io
import secrets

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import expect, sync_playwright

from app.access import AccessControl
from app.main import app


def main():
    screenshot = Image.new("RGB", (1500, 500), "white")
    draw = ImageDraw.Draw(screenshot)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
    for index, line in enumerate([
        "An educator wants to update the font of their entire Google Site.",
        "Which of these features would accomplish this?", "Preview", "Pages", "Settings", "Theme"
    ]):
        draw.text((30, 30 + index * 65), line, font=font, fill="black")
    buffer = io.BytesIO()
    screenshot.save(buffer, format="PNG")
    password = secrets.token_urlsafe(18)
    app.state.access = AccessControl({
        "VERCEL": "1", "GCE_ACCESS_PASSWORD": password,
        "GCE_OPENAI_API_KEY": "test-only-placeholder",
    })
    client = TestClient(app, base_url="https://testserver")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path="/usr/bin/chromium", headless=True, args=["--no-sandbox"]
        )
        context = browser.new_context(viewport={"width": 1280, "height": 900}, service_workers="block")
        paths, errors, external = [], [], []

        def route_request(route):
            request = route.request
            if not request.url.startswith("https://testserver/"):
                external.append(request.url)
                route.abort()
                return
            paths.append(request.url.removeprefix("https://testserver"))
            client.cookies.clear()
            response = client.request(
                request.method, request.url, content=request.post_data_buffer,
                headers=request.all_headers(), follow_redirects=False,
            )
            route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.content)

        context.route("**/*", route_request)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("https://testserver/login")
        page.locator("#password").fill(password)
        page.locator("#loginButton").click()
        expect(page.locator("#sharedStatus")).to_have_text("공동 API 연결", timeout=15000)
        page.locator("#file").set_input_files({
            "name": "question.png", "mimeType": "image/png", "buffer": buffer.getvalue()
        })
        try:
            expect(page.locator("#resultBadge")).to_have_text("문서 일치", timeout=60000)
        except Exception:
            print("UI status:", page.locator("#status").inner_text(), flush=True)
            print("Browser errors:", errors, flush=True)
            print("Requested paths:", paths, flush=True)
            raise
        expect(page.locator(".answer-text")).to_have_text("Theme")
        assert "/api/ocr" not in paths
        assert any("/core/" in path for path in paths)
        assert any("eng.traineddata" in path for path in paths)
        assert not external, external
        assert not errors, errors
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        print("Browser OCR passed: login, real WASM OCR, automatic answer, no server image upload or CDN requests, mobile layout.", flush=True)
        browser.close()
    client.close()


if __name__ == "__main__":
    main()
