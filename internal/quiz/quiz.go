// Package quiz holds the DevOps skill-test question bank and grading logic.
package quiz

import (
	"encoding/json"
	"fmt"
	"sort"
)

// Question is a single multiple-choice item in the bank.
type Question struct {
	ID          string   `json:"id"`
	Category    string   `json:"category"`
	Difficulty  string   `json:"difficulty"`
	Question    string   `json:"question"`
	Options     []string `json:"options"`
	Answer      int      `json:"answer"` // index into Options of the correct choice
	Explanation string   `json:"explanation"`
}

// PublicQuestion is a Question with the correct answer and explanation stripped,
// safe to send to the browser during a quiz.
type PublicQuestion struct {
	ID         string   `json:"id"`
	Category   string   `json:"category"`
	Difficulty string   `json:"difficulty"`
	Question   string   `json:"question"`
	Options    []string `json:"options"`
}

// Bank is an immutable, indexed collection of questions.
type Bank struct {
	questions []Question
	byID      map[string]Question
}

// NewBank builds a Bank from decoded JSON bytes, validating each question.
func NewBank(data []byte) (*Bank, error) {
	var qs []Question
	if err := json.Unmarshal(data, &qs); err != nil {
		return nil, fmt.Errorf("decode questions: %w", err)
	}
	if len(qs) == 0 {
		return nil, fmt.Errorf("question bank is empty")
	}
	byID := make(map[string]Question, len(qs))
	for i, q := range qs {
		if q.ID == "" {
			return nil, fmt.Errorf("question %d: missing id", i)
		}
		if _, dup := byID[q.ID]; dup {
			return nil, fmt.Errorf("duplicate question id %q", q.ID)
		}
		if len(q.Options) < 2 {
			return nil, fmt.Errorf("question %q: needs at least 2 options", q.ID)
		}
		if q.Answer < 0 || q.Answer >= len(q.Options) {
			return nil, fmt.Errorf("question %q: answer index %d out of range", q.ID, q.Answer)
		}
		byID[q.ID] = q
	}
	return &Bank{questions: qs, byID: byID}, nil
}

// Len reports how many questions the bank holds.
func (b *Bank) Len() int { return len(b.questions) }

// Categories returns the distinct categories, sorted alphabetically.
func (b *Bank) Categories() []string {
	seen := map[string]struct{}{}
	for _, q := range b.questions {
		seen[q.Category] = struct{}{}
	}
	cats := make([]string, 0, len(seen))
	for c := range seen {
		cats = append(cats, c)
	}
	sort.Strings(cats)
	return cats
}

// Quiz returns up to count public questions, optionally filtered by category
// ("" or "All" means every category). Selection is deterministic (bank order)
// so grading stays reproducible without server-side session state.
func (b *Bank) Quiz(category string, count int) []PublicQuestion {
	var out []PublicQuestion
	for _, q := range b.questions {
		if category != "" && category != "All" && q.Category != category {
			continue
		}
		out = append(out, PublicQuestion{
			ID:         q.ID,
			Category:   q.Category,
			Difficulty: q.Difficulty,
			Question:   q.Question,
			Options:    q.Options,
		})
		if count > 0 && len(out) >= count {
			break
		}
	}
	return out
}

// Answer is one submitted response: a question ID and the chosen option index.
type Answer struct {
	QuestionID string `json:"questionId"`
	Selected   int    `json:"selected"`
}

// Feedback reports whether a single answer was correct.
type Feedback struct {
	QuestionID  string `json:"questionId"`
	Question    string `json:"question"`
	Correct     bool   `json:"correct"`
	Selected    int    `json:"selected"`
	CorrectIdx  int    `json:"correctIndex"`
	Explanation string `json:"explanation"`
}

// Result is the graded outcome of a submission.
type Result struct {
	Total    int        `json:"total"`
	Correct  int        `json:"correct"`
	Score    int        `json:"score"` // percentage 0-100
	Feedback []Feedback `json:"feedback"`
}

// Grade scores a set of answers against the bank. Unknown question IDs are skipped.
func (b *Bank) Grade(answers []Answer) Result {
	res := Result{}
	for _, a := range answers {
		q, ok := b.byID[a.QuestionID]
		if !ok {
			continue
		}
		correct := a.Selected == q.Answer
		if correct {
			res.Correct++
		}
		res.Total++
		res.Feedback = append(res.Feedback, Feedback{
			QuestionID:  q.ID,
			Question:    q.Question,
			Correct:     correct,
			Selected:    a.Selected,
			CorrectIdx:  q.Answer,
			Explanation: q.Explanation,
		})
	}
	if res.Total > 0 {
		res.Score = res.Correct * 100 / res.Total
	}
	return res
}
