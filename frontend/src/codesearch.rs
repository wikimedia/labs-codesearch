/*
Copyright (C) 2020 Kunal Mehta <legoktm@member.fsf.org>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
*/
/// codesearch querying "library" (nothing seed specific)
use anyhow::Result;
use reqwest::Client;
use serde::Deserialize;
use std::collections::{BTreeMap, HashMap};

#[derive(Deserialize)]
pub struct HoundResponse {
    #[serde(rename = "Error")]
    pub error: Option<String>,
    #[serde(rename = "Results")]
    pub results: Option<HoundResults>,
    /*#[serde(rename = "Stats")]
    stats: Option<HoundStats>,*/
}

pub type HoundResults = HashMap<String, RepoResult>;

#[derive(Deserialize, Clone)]
pub struct RepoResult {
    #[serde(rename = "Matches")]
    pub matches: Vec<RepoMatch>,
    #[serde(rename = "FilesWithMatch")]
    pub files_with_match: usize,
    #[serde(rename = "Revision")]
    pub revision: String,
}

#[derive(Deserialize, Clone)]
pub struct RepoMatch {
    #[serde(rename = "Filename")]
    pub(crate) filename: String,
    #[serde(rename = "Matches")]
    pub(crate) matches: Vec<Match>,
}

#[derive(Deserialize, Clone)]
pub struct Match {
    #[serde(rename = "Line")]
    line: String,
    #[serde(rename = "LineNumber")]
    line_number: u32,
    #[serde(rename = "Before")]
    before: Vec<String>,
    #[serde(rename = "After")]
    after: Vec<String>,
}

/*#[derive(Deserialize)]
struct HoundStats {
    #[serde(rename = "FilesOpened")]
    files_opened: u32,
    #[serde(rename = "Duration")]
    duration: u32,
}*/

pub fn backends() -> Vec<(String, String)> {
    vec![
        ("search".to_string(), "Everything".to_string()),
        ("core".to_string(), "MediaWiki core".to_string()),
        ("extensions".to_string(), "Extensions".to_string()),
        ("skins".to_string(), "Skins".to_string()),
        ("things".to_string(), "Extensions & things".to_string()),
        ("bundled".to_string(), "MW tarball".to_string()),
        ("deployed".to_string(), "Wikimedia deployed".to_string()),
        ("libraries".to_string(), "PHP libraries".to_string()),
        ("operations".to_string(), "Wikimedia Operations".to_string()),
        ("ooui".to_string(), "OOUI".to_string()),
        ("milkshake".to_string(), "Milkshake".to_string()),
        ("pywikibot".to_string(), "Pywikibot".to_string()),
        ("services".to_string(), "Wikimedia Services".to_string()),
        ("analytics".to_string(), "Analytics".to_string()),
    ]
}

pub fn is_valid_backend(profile: &str) -> bool {
    for (backend, _) in backends() {
        if &backend == profile {
            return true;
        }
    }

    false
}

#[derive(Clone, Debug)]
pub struct SearchOptions {
    pub query: String,
    pub files: String,
    pub repos: Option<String>,
    pub case_insensitive: bool,
}

// TODO: move to separate library
pub async fn send_query(
    options: &SearchOptions,
    profile: &str,
) -> Result<HoundResponse> {
    let opts = options.clone();
    let case_insensitive = if opts.case_insensitive {
        "fosho"
    } else {
        "nope"
    };
    // offset to query
    let rng = if opts.repos.is_some() { "20:" } else { ":20" };
    let resp = Client::new()
        .get(&format!(
            "https://codesearch.wmcloud.org/{}/api/v1/search",
            profile
        ))
        // stats=fosho&repos=*&rng=%3A20&q=class+LinkRenderer%5Cb&files=&i=nope
        .query(&[
            ("stats", "fosho"),
            ("repos", &opts.repos.unwrap_or("*".to_string())),
            ("rng", rng),
            ("q", &opts.query),
            ("files", &opts.files),
            ("i", case_insensitive),
        ])
        .send()
        .await?
        .json()
        .await?;
    Ok(resp)
}

pub type HoundConfig = HashMap<String, RepoConfig>;

#[derive(Deserialize)]
pub struct RepoConfig {
    pub url: String,
    #[serde(rename = "url-pattern")]
    pub url_pattern: UrlPattern,
}

#[derive(Deserialize)]
pub struct UrlPattern {
    #[serde(rename = "base-url")]
    pub base_url: String,
    pub anchor: String,
}

pub async fn fetch_config(profile: &str) -> Result<HoundConfig> {
    let resp = Client::new()
        .get(&format!(
            "https://codesearch.wmcloud.org/{}/api/v1/repos",
            profile
        ))
        .send()
        .await?
        .json()
        .await?;

    Ok(resp)
}

/// Represent matches in a more straightforward format for display
pub fn flatten(repomatch: &RepoMatch) -> File {
    let mut file = File::new(&repomatch.filename);
    for match_ in &repomatch.matches {
        // TODO: we need separators between non-consecutive lines
        file.lines.insert(
            match_.line_number,
            Line {
                highlight: true,
                text: match_.line.to_string(),
            },
        );
        // We hardcode that the length of before and after is 2
        // But if the before line already exists, we don't want to
        // overwrite highlight
        let before_length = match_.before.len();
        if before_length >= 1 {
            if !file.lines.contains_key(&(&match_.line_number - 2)) {
                file.lines.insert(
                    match_.line_number - 2,
                    Line {
                        highlight: false,
                        text: match_.before[0].to_string(),
                    },
                );
            }
        }

        if before_length == 2 {
            if !file.lines.contains_key(&(&match_.line_number - 1)) {
                file.lines.insert(
                    match_.line_number - 1,
                    Line {
                        highlight: false,
                        text: match_.before[1].to_string(),
                    },
                );
            }
        }
        let after_length = match_.after.len();
        if after_length >= 1 {
            file.lines.insert(
                match_.line_number + 1,
                Line {
                    highlight: false,
                    text: match_.after[0].to_string(),
                },
            );
        }

        if after_length == 2 {
            file.lines.insert(
                match_.line_number + 2,
                Line {
                    highlight: false,
                    text: match_.after[1].to_string(),
                },
            );
        }
    }

    file
}

pub struct File {
    pub name: String,
    // We use BTreeMap for its built-in ordering
    pub lines: BTreeMap<u32, Line>,
}

impl File {
    fn new(name: &str) -> Self {
        Self {
            name: name.to_string(),
            lines: BTreeMap::new(),
        }
    }
}

pub struct Line {
    pub highlight: bool,
    pub text: String,
}
