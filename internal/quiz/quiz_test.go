package quiz

import (
	"os"
	"path/filepath"
	"testing"
)

const sample = `[
  {"id":"q1","category":"Docker","difficulty":"easy","question":"Base image instruction?","options":["FROM","BASE"],"answer":0,"explanation":"FROM sets the base."},
  {"id":"q2","category":"Linux","difficulty":"easy","question":"Print working dir?","options":["ls","pwd","cd"],"answer":1,"explanation":"pwd prints it."}
]`

func mustBank(t *testing.T, data string) *Bank {
	t.Helper()
	b, err := NewBank([]byte(data))
	if err != nil {
		t.Fatalf("NewBank: %v", err)
	}
	return b
}

func TestNewBankValidation(t *testing.T) {
	cases := map[string]string{
		"empty array":     `[]`,
		"bad json":        `not json`,
		"duplicate id":    `[{"id":"a","options":["x","y"],"answer":0},{"id":"a","options":["x","y"],"answer":0}]`,
		"answer range":    `[{"id":"a","options":["x","y"],"answer":5}]`,
		"too few options": `[{"id":"a","options":["x"],"answer":0}]`,
		"missing id":      `[{"options":["x","y"],"answer":0}]`,
	}
	for name, data := range cases {
		t.Run(name, func(t *testing.T) {
			if _, err := NewBank([]byte(data)); err == nil {
				t.Fatalf("expected error for %s", name)
			}
		})
	}
}

func TestCategories(t *testing.T) {
	b := mustBank(t, sample)
	got := b.Categories()
	want := []string{"Docker", "Linux"}
	if len(got) != len(want) {
		t.Fatalf("got %v, want %v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("category[%d] = %q, want %q (should be sorted)", i, got[i], want[i])
		}
	}
}

func TestQuizFilterAndCount(t *testing.T) {
	b := mustBank(t, sample)

	if n := len(b.Quiz("Docker", 0)); n != 1 {
		t.Errorf("Docker filter returned %d questions, want 1", n)
	}
	if n := len(b.Quiz("All", 0)); n != 2 {
		t.Errorf("All returned %d, want 2", n)
	}
	if n := len(b.Quiz("", 1)); n != 1 {
		t.Errorf("count=1 returned %d, want 1", n)
	}
	// Public questions must not leak the answer.
	for _, q := range b.Quiz("Docker", 0) {
		if q.ID == "" || q.Question == "" {
			t.Error("public question missing fields")
		}
	}
}

func TestGrade(t *testing.T) {
	b := mustBank(t, sample)
	res := b.Grade([]Answer{
		{QuestionID: "q1", Selected: 0},   // correct
		{QuestionID: "q2", Selected: 0},   // wrong (answer is 1)
		{QuestionID: "nope", Selected: 0}, // unknown, skipped
	})
	if res.Total != 2 {
		t.Errorf("Total = %d, want 2 (unknown id skipped)", res.Total)
	}
	if res.Correct != 1 {
		t.Errorf("Correct = %d, want 1", res.Correct)
	}
	if res.Score != 50 {
		t.Errorf("Score = %d, want 50", res.Score)
	}
	if len(res.Feedback) != 2 {
		t.Fatalf("Feedback len = %d, want 2", len(res.Feedback))
	}
	if !res.Feedback[0].Correct || res.Feedback[1].Correct {
		t.Error("feedback correctness flags are wrong")
	}
	if res.Feedback[1].CorrectIdx != 1 {
		t.Errorf("expected correct index 1, got %d", res.Feedback[1].CorrectIdx)
	}
}

func TestGradeEmpty(t *testing.T) {
	b := mustBank(t, sample)
	if res := b.Grade(nil); res.Score != 0 || res.Total != 0 {
		t.Errorf("empty grade should be zero, got %+v", res)
	}
}

// TestRealBank ensures the shipped data file loads and validates.
func TestRealBank(t *testing.T) {
	path := filepath.Join("..", "..", "data", "questions.json")
	data, err := os.ReadFile(path)
	if err != nil {
		t.Skipf("questions.json not found: %v", err)
	}
	b, err := NewBank(data)
	if err != nil {
		t.Fatalf("shipped question bank is invalid: %v", err)
	}
	if b.Len() < 10 {
		t.Errorf("expected a substantial bank, got %d questions", b.Len())
	}
}
