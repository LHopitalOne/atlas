use crate::model::HnComment;

/// Strip the tiny bit of HTML that HN puts in comment bodies.
fn plain(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    let mut in_tag = false;
    for ch in text.chars() {
        match ch {
            '<' => in_tag = true,
            '>' => {
                in_tag = false;
                out.push(' ');
            }
            _ if !in_tag => out.push(ch),
            _ => {}
        }
    }
    out.replace("&#x27;", "'").replace("&quot;", "\"").replace("&amp;", "&")
}

fn first_sentence(text: &str, max_words: usize) -> String {
    let words: Vec<&str> = text.split_whitespace().take(max_words).collect();
    let joined = words.join(" ");
    match joined.find(". ") {
        Some(idx) => joined[..=idx].to_string(),
        None => joined,
    }
}

/// Extractive "summary": the title plus the opening line of each top comment.
pub fn summarize(title: &str, comments: &[HnComment]) -> String {
    let mut lines = vec![format!("{title}.")];
    for c in comments {
        if let Some(text) = &c.text {
            let who = c.by.as_deref().unwrap_or("someone");
            lines.push(format!("{who}: {}", first_sentence(&plain(text), 24)));
        }
    }
    if comments.is_empty() {
        lines.push("No discussion yet.".into());
    }
    lines.join(" ")
}
