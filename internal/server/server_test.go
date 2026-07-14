package server

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"testing/fstest"

	"github.com/skybytescode/skillbox/internal/quiz"
)

const sample = `[
  {"id":"q1","category":"Docker","difficulty":"easy","question":"Base image?","options":["FROM","BASE"],"answer":0,"explanation":"FROM."},
  {"id":"q2","category":"Linux","difficulty":"easy","question":"Print dir?","options":["ls","pwd"],"answer":1,"explanation":"pwd."}
]`

func testServer(t *testing.T) http.Handler {
	t.Helper()
	bank, err := quiz.NewBank([]byte(sample))
	if err != nil {
		t.Fatalf("bank: %v", err)
	}
	web := fstest.MapFS{"index.html": {Data: []byte("<h1>hi</h1>")}}
	return New(bank, web).Routes()
}

func TestCategoriesEndpoint(t *testing.T) {
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/categories", nil)
	testServer(t).ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("status = %d", rr.Code)
	}
	var body struct {
		Categories []string `json:"categories"`
		Total      int      `json:"total"`
	}
	if err := json.Unmarshal(rr.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body.Total != 2 || len(body.Categories) != 2 {
		t.Errorf("unexpected categories body: %+v", body)
	}
}

func TestQuizEndpointHidesAnswer(t *testing.T) {
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/quiz?category=Docker&count=5", nil)
	testServer(t).ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("status = %d", rr.Code)
	}
	if strings.Contains(rr.Body.String(), "\"answer\"") {
		t.Error("quiz response leaked the correct answer field")
	}
	if !strings.Contains(rr.Body.String(), "q1") {
		t.Error("expected Docker question q1 in response")
	}
}

func TestQuizBadCount(t *testing.T) {
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/quiz?count=-3", nil)
	testServer(t).ServeHTTP(rr, req)
	if rr.Code != http.StatusBadRequest {
		t.Errorf("status = %d, want 400", rr.Code)
	}
}

func TestSubmitEndpoint(t *testing.T) {
	body := `{"answers":[{"questionId":"q1","selected":0},{"questionId":"q2","selected":0}]}`
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/api/submit", strings.NewReader(body))
	testServer(t).ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("status = %d", rr.Code)
	}
	var res quiz.Result
	if err := json.Unmarshal(rr.Body.Bytes(), &res); err != nil {
		t.Fatal(err)
	}
	if res.Total != 2 || res.Correct != 1 || res.Score != 50 {
		t.Errorf("unexpected result: %+v", res)
	}
}

func TestSubmitEmpty(t *testing.T) {
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/api/submit", strings.NewReader(`{"answers":[]}`))
	testServer(t).ServeHTTP(rr, req)
	if rr.Code != http.StatusBadRequest {
		t.Errorf("status = %d, want 400", rr.Code)
	}
}

func TestStaticIndex(t *testing.T) {
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	testServer(t).ServeHTTP(rr, req)
	if rr.Code != http.StatusOK || !strings.Contains(rr.Body.String(), "hi") {
		t.Errorf("index not served: status %d", rr.Code)
	}
}
