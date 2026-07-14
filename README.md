# 🚀 SkillBox — DevOps Skill Test

A small, self-contained **web application for testing DevOps knowledge**, inspired by the
curriculum of the [Skillbox DevOps Engineer profession](https://go.skillbox.ru/profession/profession-dev-ops-2/devops-course).

Answer multiple-choice questions across the core areas of a DevOps engineer's toolkit and get an
instant, graded result with explanations for every question.

![Go](https://img.shields.io/badge/Go-1.22%2B-00ADD8?logo=go&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

## Topics covered

The question bank spans **10 categories** of the DevOps curriculum:

| | | |
|---|---|---|
| 🐧 Linux | 💻 Bash | 🌐 Networking |
| 🔀 Git | 🐳 Docker | ☸️ Kubernetes |
| 🔁 CI/CD | 📕 Ansible | 🏗️ Terraform |
| 📊 Monitoring | | |

Each question has a difficulty (`easy` / `medium` / `hard`) and an explanation shown in the review.

## Features

- **Web UI** — pick a category and question count, answer in the browser, get a scored result.
- **Server-side grading** — correct answers never leave the server during a quiz, so they can't be inspected in the browser.
- **Single binary** — questions and web assets are embedded via `go:embed`; nothing external to deploy.
- **REST API** — clean JSON endpoints you can script against.
- **Tested** — unit tests for the grading logic and HTTP handlers.

## Quick start

```bash
git clone https://github.com/skybytescode/skillbox.git
cd skillbox
go run .
```

Then open <http://localhost:8080> in your browser.

Change the port with the `PORT` environment variable:

```bash
PORT=9000 go run .
```

### Build a binary

```bash
go build -o skillbox .
./skillbox
```

### Run with Docker

```bash
docker build -t skillbox .
docker run -p 8080:8080 skillbox
```

## REST API

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/categories` | List categories and total question count |
| `GET`  | `/api/quiz?category=<name>&count=<n>` | Get questions (answers stripped). `category=All` or empty for all; `count=0` for all matching |
| `POST` | `/api/submit` | Grade answers, returns score and per-question feedback |
| `GET`  | `/healthz` | Health check |

**Submit example:**

```bash
curl -s -X POST http://localhost:8080/api/submit \
  -H 'Content-Type: application/json' \
  -d '{"answers":[{"questionId":"docker-1","selected":1}]}'
```

```json
{
  "total": 1,
  "correct": 1,
  "score": 100,
  "feedback": [
    {
      "questionId": "docker-1",
      "correct": true,
      "correctIndex": 1,
      "explanation": "`FROM` declares the base image for the build stage."
    }
  ]
}
```

## Project structure

```
skillbox/
├── main.go                  # entrypoint: embeds assets, starts the HTTP server
├── data/
│   └── questions.json       # the question bank
├── internal/
│   ├── quiz/                # question model, validation, grading logic (+ tests)
│   └── server/              # HTTP handlers and routing (+ tests)
└── web/                     # embedded front-end (HTML/CSS/JS)
    ├── index.html
    └── static/
        ├── style.css
        └── app.js
```

## Adding questions

Edit [`data/questions.json`](data/questions.json) and add an object:

```json
{
  "id": "docker-6",
  "category": "Docker",
  "difficulty": "medium",
  "question": "Which command lists running containers?",
  "options": ["docker ps", "docker ls", "docker top", "docker run"],
  "answer": 0,
  "explanation": "`docker ps` lists running containers; add -a for all."
}
```

- `id` must be unique.
- `answer` is the **zero-based index** into `options`.
- The bank is validated at startup — a bad index or duplicate id fails fast.

## Running tests

```bash
go test ./...
```

## License

[MIT](LICENSE) — free to use, learn from, and extend.

---

> Not affiliated with Skillbox. This is an independent, educational project inspired by a public course outline.
