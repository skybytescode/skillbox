// Command skillbox runs a DevOps skill-test web application.
//
// It serves a browser quiz covering the core topics of a DevOps engineer
// curriculum: Linux, Bash, Networking, Git, Docker, Kubernetes, CI/CD,
// Ansible, Terraform, and Monitoring. Questions are graded server-side.
package main

import (
	"embed"
	"io/fs"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/skybytescode/skillbox/internal/quiz"
	"github.com/skybytescode/skillbox/internal/server"
)

//go:embed data/questions.json
var questionData []byte

//go:embed web
var webFiles embed.FS

func main() {
	bank, err := quiz.NewBank(questionData)
	if err != nil {
		log.Fatalf("load question bank: %v", err)
	}

	webFS, err := fs.Sub(webFiles, "web")
	if err != nil {
		log.Fatalf("mount web assets: %v", err)
	}

	addr := ":" + port()
	srv := &http.Server{
		Addr:              addr,
		Handler:           server.New(bank, webFS).Routes(),
		ReadHeaderTimeout: 5 * time.Second,
	}

	log.Printf("SkillBox DevOps quiz: %d questions across %d categories", bank.Len(), len(bank.Categories()))
	log.Printf("listening on http://localhost%s", addr)
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("server error: %v", err)
	}
}

func port() string {
	if p := os.Getenv("PORT"); p != "" {
		return p
	}
	return "8080"
}
