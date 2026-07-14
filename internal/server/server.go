// Package server exposes the DevOps skill-test quiz over HTTP.
package server

import (
	"encoding/json"
	"io/fs"
	"net/http"
	"strconv"

	"github.com/skybytescode/skillbox/internal/quiz"
)

// Server wires the question bank and static web assets to HTTP handlers.
type Server struct {
	bank *quiz.Bank
	web  fs.FS
}

// New creates a Server backed by the given bank and static file system.
func New(bank *quiz.Bank, web fs.FS) *Server {
	return &Server{bank: bank, web: web}
}

// Routes returns the configured HTTP handler.
func (s *Server) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/categories", s.handleCategories)
	mux.HandleFunc("GET /api/quiz", s.handleQuiz)
	mux.HandleFunc("POST /api/submit", s.handleSubmit)
	mux.HandleFunc("GET /healthz", s.handleHealth)
	mux.Handle("GET /", http.FileServer(http.FS(s.web)))
	return mux
}

func (s *Server) handleHealth(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (s *Server) handleCategories(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"categories": s.bank.Categories(),
		"total":      s.bank.Len(),
	})
}

func (s *Server) handleQuiz(w http.ResponseWriter, r *http.Request) {
	category := r.URL.Query().Get("category")
	count := 0
	if c := r.URL.Query().Get("count"); c != "" {
		n, err := strconv.Atoi(c)
		if err != nil || n < 0 {
			writeError(w, http.StatusBadRequest, "count must be a non-negative integer")
			return
		}
		count = n
	}
	questions := s.bank.Quiz(category, count)
	writeJSON(w, http.StatusOK, map[string]any{"questions": questions})
}

func (s *Server) handleSubmit(w http.ResponseWriter, r *http.Request) {
	var payload struct {
		Answers []quiz.Answer `json:"answers"`
	}
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20)).Decode(&payload); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}
	if len(payload.Answers) == 0 {
		writeError(w, http.StatusBadRequest, "no answers submitted")
		return
	}
	result := s.bank.Grade(payload.Answers)
	writeJSON(w, http.StatusOK, result)
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}
