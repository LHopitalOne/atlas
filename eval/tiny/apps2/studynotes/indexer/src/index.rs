use std::collections::{HashMap, HashSet};

/// Tiny in-memory inverted index: term -> note ids, plus note id -> terms
/// so a note can be re-indexed or removed cleanly.
#[derive(Default)]
pub struct NoteIndex {
    postings: HashMap<String, HashSet<String>>,
    terms_by_note: HashMap<String, HashSet<String>>,
}

fn tokenize(text: &str) -> HashSet<String> {
    text.split(|c: char| !c.is_alphanumeric())
        .filter(|t| t.len() > 2)
        .map(|t| t.to_lowercase())
        .collect()
}

impl NoteIndex {
    pub fn upsert(&mut self, note_id: &str, title: &str, body: &str) -> usize {
        self.remove(note_id);
        let mut terms = tokenize(title);
        terms.extend(tokenize(body));
        for term in &terms {
            self.postings
                .entry(term.clone())
                .or_default()
                .insert(note_id.to_string());
        }
        let count = terms.len();
        self.terms_by_note.insert(note_id.to_string(), terms);
        count
    }

    pub fn remove(&mut self, note_id: &str) -> bool {
        let Some(terms) = self.terms_by_note.remove(note_id) else {
            return false;
        };
        for term in terms {
            if let Some(ids) = self.postings.get_mut(&term) {
                ids.remove(note_id);
                if ids.is_empty() {
                    self.postings.remove(&term);
                }
            }
        }
        true
    }

    pub fn search(&self, query: &str, limit: usize) -> Vec<(String, f32)> {
        let wanted = tokenize(query);
        if wanted.is_empty() {
            return Vec::new();
        }
        let mut scores: HashMap<&str, f32> = HashMap::new();
        for term in &wanted {
            if let Some(ids) = self.postings.get(term) {
                for id in ids {
                    *scores.entry(id.as_str()).or_default() += 1.0;
                }
            }
        }
        let mut hits: Vec<(String, f32)> = scores
            .into_iter()
            .map(|(id, s)| (id.to_string(), s / wanted.len() as f32))
            .collect();
        hits.sort_by(|a, b| b.1.total_cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
        hits.truncate(limit.max(1));
        hits
    }
}
