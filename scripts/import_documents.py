"""Import the three supplied DOCX files; run with their containing directory."""
import json
import re
import sys
from pathlib import Path

from docx import Document

ROOT = Path(__file__).resolve().parents[1]

# Editorial suggestions, not independently web-verified answers.
CORRECTIONS = {
    1: ([3], "사이트 전체 글꼴은 Theme에서 변경합니다."),
    4: ([3], "웹캠으로 바로 촬영해 삽입하려면 Camera를 선택합니다."),
    6: ([0], "Snooze는 지정 시각에 메일을 다시 표시합니다. 라벨 자체는 알림을 예약하지 않습니다."),
    9: ([0, 1], "시각장애 학생에게 ChromeVox를, 다른 언어 사용자에게 문서 번역을 제공합니다. Viewer는 편집할 수 없습니다."),
    10: ([2], "다른 변경 사항을 보존하려면 이전 버전에서 누락된 내용만 복사해 현재 문서에 붙여넣습니다."),
    23: ([3], "업로드한 파일의 자동 변환은 Uploads 설정에 해당합니다."),
    26: ([3], "관리자가 소유권과 접근 권한을 통제하려면 소유권을 이전합니다. 조직 정책에 따른 제한은 별도로 확인해야 합니다."),
    27: ([2], "Calendar 일정에 공동 작업용 회의 문서를 첨부할 수 있습니다."),
    29: ([0], "청각장애 참가자를 위해 발표 모드의 자막을 켭니다."),
    31: ([3], "제시된 보기 중 다양한 형식의 자료를 한곳에 저장하는 기능이 가장 적합합니다. 문제의 표현은 다소 모호합니다."),
    33: ([0], "웹페이지 콘텐츠를 표시하려면 URL 또는 코드로 삽입합니다."),
    34: ([0], "관심 그룹별 과제를 만들고 해당 학생에게만 배정합니다."),
    37: ([3], "과제 수집과 루브릭 피드백은 Classroom 기능입니다."),
}


def paragraphs(path):
    return [p.text.strip() for p in Document(path).paragraphs if p.text.strip()]


def answers(path):
    result = {}
    current = None
    for line in paragraphs(path):
        match = re.match(r"^(\d+)\.\s*(.*)", line, re.S)
        if match:
            current = int(match[1])
            result[current] = match[2]
        elif current:
            result[current] += "\n" + line
    return result


def main(directory):
    files = {p.name: p for p in Path(directory).rglob("*.docx")}
    question_file = files["GCE_Level1_Questions_and_Tasks.docx"]
    answer_file = files["GCE_Level1_Answers.docx"]
    level2_file = files["GCE_Level2_Answers_Corrected.docx"]
    key = answers(answer_file)
    entries = []
    tasks = []
    current = None
    task_mode = False
    for line in paragraphs(question_file):
        if line == "Tasks":
            task_mode = True
            current = None
            continue
        if task_mode:
            match = re.match(r"Task (\d+)\.\s*(.*)", line)
            if match:
                current = {"id": f"task-{match[1]}", "title": match[2], "steps": []}
                tasks.append(current)
            elif current:
                current["steps"].append(line)
            continue
        match = re.match(r"^(\d+)\.\s*(.*)", line)
        if match:
            number = int(match[1])
            current = {
                "id": f"l1-{number}", "level": 1, "number": number,
                "question": match[2], "options": [], "original_answer": key[number],
                "source": answer_file.name, "question_source": question_file.name,
                "verification": "document_only",
            }
            entries.append(current)
        elif current and line.startswith("-"):
            current["options"].append(line[1:].strip())
    for entry in entries:
        entry["answer"] = entry["original_answer"]
        if entry["number"] in CORRECTIONS:
            indices, reason = CORRECTIONS[entry["number"]]
            entry["answer"] = "\n".join(entry["options"][i] for i in indices)
            entry["correction_reason"] = reason
            entry["verification"] = "editorial_suggestion"
    for number, answer in answers(level2_file).items():
        entries.append({
            "id": f"l2-{number}", "level": 2, "number": number, "question": None,
            "options": [], "answer": answer, "original_answer": answer,
            "source": level2_file.name, "verification": "answer_only",
        })
    output = {"entries": entries, "tasks": tasks}
    (ROOT / "data" / "questions.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Imported {len(entries)} answer records and {len(tasks)} tasks")


if __name__ == "__main__":
    main(sys.argv[1])
