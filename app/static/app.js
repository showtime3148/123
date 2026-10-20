const $ = id => document.getElementById(id);
let apiKey = "", model = "gpt-4.1-mini", database = null, busy = false;
let sharedMode = false;
let browserOcr = false;
let configReady;
const element = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};
function status(message, error = false) {
  $("status").textContent = message;
  $("status").className = error ? "error" : "";
}
function setBusy(value) {
  busy = value;
  for (const id of ["search", "capture", "clear", "file"]) $(id).disabled = value;
  $("question").disabled = value;
  $("result").setAttribute("aria-busy", String(value));
}
async function request(path, body) {
  const response = await fetch(path, {
    method: "POST", headers: {"Content-Type": "application/json", "X-API-Key": apiKey},
    body: JSON.stringify(body), signal: AbortSignal.timeout(100000)
  });
  const data = await response.json();
  if (response.status === 401) { location.replace("/login"); throw new Error("다시 로그인해 주세요."); }
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "입력 형식을 확인해 주세요.");
  return data;
}
function details(title, content) {
  const node = element("details");
  node.append(element("summary", title), element("p", content));
  return node;
}
function webButton() {
  const button = element("button", "웹 출처로 다시 검증 ↗", "secondary");
  button.addEventListener("click", () => search(true));
  return button;
}
function renderResult(data) {
  if (data.usage) showUsage(data.usage);
  const target = $("result");
  target.replaceChildren();
  if (data.mode === "local") {
    const row = data.match;
    $("resultBadge").textContent = "문서 일치";
    target.append(element("div", `LEVEL ${row.level} · ${row.number}번 · 텍스트 유사도 ${Math.round(row.similarity * 100)}%`, "answer-label"));
    target.append(element("div", row.answer, "answer-text"));
    if (row.correction_reason) {
      target.append(element("div", `수정 제안 · ${row.correction_reason}\n웹에서 검증한 답은 아닙니다.`, "explanation"));
    } else {
      target.append(element("p", "첨부 정답지에 기록된 답입니다. 정답 정확도를 웹에서 별도로 검증할 수 있습니다.", "note"));
    }
    target.append(details("매칭된 문제와 보기", row.question + "\n\n" + row.options.join("\n")));
    target.append(details("정답지 원본 답", row.original_answer));
    target.append(element("p", `자료: ${row.source} · 유사도는 정답 확률이 아닙니다.`, "source"));
    target.append(webButton());
  } else if (data.mode === "web") {
    $("resultBadge").textContent = "웹 검색";
    target.append(element("div", "검색 근거가 포함된 답변", "answer-label"));
    target.append(element("div", data.answer, "answer-text web-answer"));
    const sources = element("div", undefined, "sources");
    sources.append(element("strong", "출처"));
    for (const source of data.sources) {
      const link = element("a", source.title);
      if (!source.url.startsWith("https://")) continue;
      link.href = source.url; link.target = "_blank"; link.rel = "noopener noreferrer";
      sources.append(link);
    }
    target.append(sources);
  } else {
    $("resultBadge").textContent = "연결 필요";
    target.append(element("p", data.message));
    if (sharedMode) {
      target.append(element("p", "공동 API 연결을 관리자에게 확인해 주세요.", "note"));
    } else {
      const button = element("button", "API 설정 열기", "secondary");
      button.onclick = () => $("settings").showModal();
      target.append(button);
    }
  }
  if (data.mode !== "local" && data.candidates?.length) {
    target.append(details("참고: 유사한 문서 문제 (정답 매칭 아님)", data.candidates.map(row =>
      `${row.number}번 · 유사도 ${Math.round(row.similarity * 100)}%\n${row.question}`).join("\n\n")));
  }
}
async function search(forceWeb = false) {
  if (busy) return;
  const text = $("question").value.trim();
  if (text.length < 8) return status("문제와 보기를 입력해 주세요.", true);
  setBusy(true);
  $("result").replaceChildren();
  $("resultBadge").textContent = "검색 중";
  status(forceWeb ? "웹에서 공식 자료를 검색하고 있습니다…" : "문서를 찾고 있습니다. 필요하면 웹 검색으로 이어집니다…");
  try {
    renderResult(await request("/api/answer", {text, force_web: forceWeb, model}));
    status("");
  } catch (error) {
    status(error.name === "TimeoutError" ? "검색 시간이 초과되었습니다. 다시 시도해 주세요." : error.message, true);
    $("resultBadge").textContent = "확인 필요";
  } finally { setBusy(false); }
}
async function loadImage(file) {
  if (busy || !file) return;
  if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) return status("PNG, JPG, WebP 이미지를 선택해 주세요.", true);
  if (file.size > 8000000) return status("8MB 이하의 이미지를 선택해 주세요.", true);
  setBusy(true); status("화면에서 영어 문제를 읽고 있습니다…");
  $("result").replaceChildren(); $("resultBadge").textContent = "문자 인식";
  let success = false;
  try {
    if (!await configReady) throw new Error("앱 설정을 읽지 못했습니다. 새로고침 후 다시 시도해 주세요.");
    const data = await new Promise((resolve, reject) => {
      const reader = new FileReader(); reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error("파일을 읽을 수 없습니다.")); reader.readAsDataURL(file);
    });
    $("preview").src = data; $("preview").hidden = false;
    if (browserOcr) {
      $("question").value = await recognizeScreenshot(data, message => status(message));
    } else {
      $("question").value = (await request("/api/ocr", {image: data})).text;
    }
    success = true;
  } catch (error) { status(error.message, true); $("resultBadge").textContent = "확인 필요"; }
  finally { setBusy(false); }
  if (success) await search();
}
$("file").addEventListener("change", event => loadImage(event.target.files[0]));
$("dropzone").onclick = () => { if (!busy) $("file").click(); };
$("dropzone").onkeydown = event => {
  if (["Enter", " "].includes(event.key)) { event.preventDefault(); if (!busy) $("file").click(); }
};
for (const type of ["dragenter", "dragover"]) $("dropzone").addEventListener(type, event => {event.preventDefault(); $("dropzone").classList.add("drag");});
$("dropzone").ondragleave = () => $("dropzone").classList.remove("drag");
$("dropzone").ondrop = event => {
  event.preventDefault(); $("dropzone").classList.remove("drag"); loadImage(event.dataTransfer.files[0]);
};
document.addEventListener("paste", event => {
  const image = [...(event.clipboardData?.items || [])].find(item => item.type.startsWith("image/"));
  if (image) { event.preventDefault(); loadImage(image.getAsFile()); }
});
$("capture").onclick = async () => {
  if (!navigator.mediaDevices?.getDisplayMedia) return status("이 브라우저는 화면 캡처를 지원하지 않습니다. 캡처 이미지를 붙여넣어 주세요.", true);
  let stream;
  try {
    stream = await navigator.mediaDevices.getDisplayMedia({video: true, audio: false});
    const video = document.createElement("video");
    video.srcObject = stream; video.muted = true; await video.play();
    await new Promise(resolve => video.requestVideoFrameCallback ? video.requestVideoFrameCallback(resolve) : setTimeout(resolve, 300));
    const canvas = document.createElement("canvas"); canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    stream.getTracks().forEach(track => track.stop());
    const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/png"));
    await loadImage(blob);
  } catch (error) {
    status(error.name === "NotAllowedError" ? "화면 캡처가 취소되었습니다. 이미지를 올리거나 문제를 입력할 수 있습니다." : "캡처에 실패했습니다. 이미지를 직접 올려 주세요.", true);
  } finally { stream?.getTracks().forEach(track => track.stop()); }
};
$("search").onclick = () => search();
$("clear").onclick = () => {
  $("question").value = ""; $("preview").hidden = true; $("preview").removeAttribute("src");
  $("file").value = ""; $("result").replaceChildren(); $("resultBadge").textContent = "준비됨"; status("");
};
$("settingsButton").onclick = () => $("settings").showModal();
$("closeSettings").onclick = () => $("settings").close();
$("settingsForm").onsubmit = event => {
  event.preventDefault(); apiKey = $("apiKey").value.trim(); model = $("model").value.trim();
  $("keyStatus").textContent = apiKey ? "키 입력됨" : "미연결"; $("settings").close();
  status("설정을 저장했습니다. ‘답 찾기’ 또는 ‘웹 출처로 다시 검증’을 눌러 주세요.");
};
$("forgetKey").onclick = () => { apiKey = ""; $("apiKey").value = ""; $("keyStatus").textContent = "미연결"; };
$("logout").onclick = async () => {
  try {
    await request("/api/logout", {});
    apiKey = ""; $("apiKey").value = ""; location.replace("/login");
  } catch (error) { status(error.message, true); }
};
function showUsage(usage) {
  $("sharedStatus").textContent = usage ? `공동 검색 ${usage.used} / ${usage.limit}회 · 오늘` : "공동 API 연결";
}
function renderLibrary(tab = "1") {
  const container = $("library"); container.replaceChildren();
  const rows = tab === "tasks" ? database.tasks : database.entries.filter(row => String(row.level) === tab);
  for (const row of rows) {
    const item = element("div", undefined, "library-item");
    const body = element("div", undefined, "library-body");
    item.append(element("span", String(row.number || row.id.split("-")[1]).padStart(2, "0"), "library-number"), body);
    if (row.correction_reason) body.append(element("span", "수정 제안", "tag"));
    body.append(element("p", row.question || row.title || row.answer));
    if (tab === "tasks") body.append(details("실습 단계 보기", row.steps.join("\n\n")));
    else if (row.question) {
      body.append(element("small", row.answer));
      const use = element("button", "불러오기", "secondary");
      use.onclick = () => {
        if (busy) return;
        $("question").value = row.question + "\n" + row.options.join("\n");
        $("question").scrollIntoView({behavior:"smooth", block:"center"}); search();
      };
      item.append(use);
    } else body.append(element("small", "문제 본문 없음 · 참고용 정답 목록"));
    container.append(item);
  }
}
document.querySelectorAll("[data-tab]").forEach(button => button.onclick = () => {
  if (!database) return;
  document.querySelectorAll("[data-tab]").forEach(node => node.classList.toggle("active", node === button));
  renderLibrary(button.dataset.tab);
});
configReady = Promise.all(["/api/library", "/api/config"].map(path => fetch(path).then(response => {
  if (response.status === 401) { location.replace("/login"); throw new Error("로그인이 필요합니다."); }
  if (!response.ok) throw new Error("학습 자료를 불러오지 못했습니다. 서버를 확인해 주세요.");
  return response.json();
}))).then(([data, config]) => {
  database = data; renderLibrary();
  sharedMode = config.key_mode === "shared";
  browserOcr = config.ocr_mode === "browser";
  model = config.model;
  $("logout").hidden = !config.login_required;
  if (config.closes_at) {
    $("deadline").hidden = false;
    $("deadline").textContent = "이용 종료: " + new Intl.DateTimeFormat("ko-KR", {
      timeZone: "Asia/Seoul", dateStyle: "short", timeStyle: "short"
    }).format(new Date(config.closes_at * 1000)) + " (한국 시간)";
  }
  if (sharedMode) {
    $("settingsButton").hidden = true;
    $("sharedStatus").hidden = false;
    showUsage(config.usage);
  }
  return true;
}).catch(error => { status(error.message, true); return false; });
