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
use seed::{prelude::*, *};

mod codesearch;
mod view;

fn init(mut url: Url, orders: &mut impl Orders<Msg>) -> Model {
    let profile = match url.next_path_part() {
        None => "search".to_string(),
        Some(part) => {
            if codesearch::is_valid_backend(part) {
                part.to_string()
            } else {
                "search".to_string()
            }
        }
    };
    let options = codesearch::SearchOptions::from(url);
    if !options.query.is_empty() {
        orders.perform_cmd(async { Msg::SearchSubmitted });
    }
    Model {
        options,
        profile,
        loading: false,
        hound_config: None,
        results: None,
        result_format: "Default".to_string(),
        error: None,
    }
}

impl From<Url> for codesearch::SearchOptions {
    fn from(url: Url) -> Self {
        let query = match url.search().get("q") {
            Some(query) => query[0].to_string(),
            None => "".to_string(),
        };
        let case_insensitive = match url.search().get("i") {
            Some(val) => val[0] == "fosho",
            _ => false,
        };
        let files = match url.search().get("files") {
            Some(path) => path[0].to_string(),
            _ => "".to_string(),
        };
        Self {
            query,
            files,
            case_insensitive,
            repos: None
        }
    }
}

/// `Model` describes our app state.
struct Model {
    options: codesearch::SearchOptions,
    profile: String,
    loading: bool,
    hound_config: Option<codesearch::HoundConfig>,
    results: Option<codesearch::HoundResults>,
    result_format: String,
    error: Option<String>,
}

impl Model {
    fn to_url(&self) -> Url {
        let case_insenstive = if self.options.case_insensitive {
            "fosho".to_string()
        } else {
            "nope".to_string()
        };
        if self.options.query.is_empty() {
            Url::new().add_path_part(&format!("{}/", self.profile))
        } else {
            Url::new()
                .add_path_part(&format!("{}/", self.profile))
                .set_search(UrlSearch::new(vec![
                    ("q", vec![&self.options.query]),
                    ("i", vec![&case_insenstive]),
                    ("files", vec![&self.options.files]),
                ]))
        }
    }
}

/// `Msg` describes the different events you can modify state with.
enum Msg {
    SearchSubmitted,
    SearchQueryChanged(String),
    FilesChanged(String),
    CaseInsensitiveChanged,
    ResultsReceived(codesearch::HoundConfig, codesearch::HoundResults),
    PartialResultsReceived(codesearch::RepoResult, String),
    ResultsErrored(String),
    ChangeProfile(String),
    ChangeResultFormat(String),
    LoadMoreResults(String),
}

fn change_url(new_url: &str) {
    util::history()
        .push_state_with_url(&JsValue::from_str("{}"), "", Some(&new_url))
        .unwrap();
}

/// `update` describes how to handle each `Msg`.
fn update(msg: Msg, model: &mut Model, orders: &mut impl Orders<Msg>) {
    match msg {
        Msg::SearchSubmitted => {
            model.error = None;
            model.results = None;
            let options = model.options.clone();

            if options.query.is_empty() {
                // Don't do anything if there is no search term
                return;
            }

            let profile = model.profile.clone();
            let url = model.to_url().to_string().clone();
            model.loading = true;
            orders.perform_cmd(async move {
                let fconfig = codesearch::fetch_config(&profile);
                let fresults = codesearch::send_query(&options, &profile);

                // Update the URLs once we've fired off our requests
                change_url(&url);

                let config = match fconfig.await {
                    Ok(config) => config,
                    Err(e) => return Msg::ResultsErrored(e.to_string()),
                };
                let resp = match fresults.await {
                    Ok(resp) => resp,
                    Err(e) => return Msg::ResultsErrored(e.to_string()),
                };
                if let Some(error) = resp.error {
                    return Msg::ResultsErrored(error);
                }

                match resp.results {
                    Some(results) => Msg::ResultsReceived(config, results),
                    None => Msg::ResultsErrored(
                        "Unknown error fetching search results".to_string(),
                    ),
                }
            });
        }
        Msg::SearchQueryChanged(val) => {
            model.options.query = val;
            // No need to re-render
            orders.skip();
        }
        Msg::FilesChanged(val) => {
            model.options.files = val;
            // No need to re-render
            orders.skip();
        }
        Msg::CaseInsensitiveChanged => {
            let current = model.options.case_insensitive;
            model.options.case_insensitive = !current;
            // No need to re-render
            orders.skip();
        }
        Msg::ResultsReceived(config, results) => {
            model.hound_config = Some(config);
            model.results = Some(results);
            model.loading = false;
        }
        Msg::ResultsErrored(error) => {
            model.error = Some(error);
            model.loading = false;
        }
        Msg::ChangeProfile(profile) => {
            model.profile = profile;
            // If we already had some results, retrigger a search
            if model.results.is_some() {
                orders.perform_cmd(async { Msg::SearchSubmitted });
            } else {
                change_url(&model.to_url().to_string());
            }
        }
        Msg::ChangeResultFormat(result_format) => {
            model.result_format = result_format;
        }
        Msg::LoadMoreResults(repo) => {
            orders.skip();
            let profile = model.profile.clone();
            let mut options = model.options.clone();
            let repo2 = repo.clone();
            options.repos = Some(repo);
            orders.perform_cmd(async move {
                let resp = match codesearch::send_query(&options, &profile).await {
                    Ok(resp) => resp,
                    Err(err) => return Msg::ResultsErrored(err.to_string())
                };
                if let Some(error) = resp.error {
                    return Msg::ResultsErrored(error);
                }

                match resp.results {
                    Some(results) => {
                        let our_results = results[&repo2].clone();
                        Msg::PartialResultsReceived(our_results, options.repos.unwrap())
                    },
                    None => Msg::ResultsErrored(
                        "Unknown error fetching search results".to_string(),
                    ),
                }
            });
        },
        Msg::PartialResultsReceived(new_results, repo) => {
            // Need to merge the results together
            if let Some(results) = model.results.as_mut() {
                //results.insert(repo, new_results);
                let repomatch = results.get_mut(&repo).unwrap();
                repomatch.matches.extend(new_results.matches.iter().cloned());
            }
        }
    }
}

/// (This function is invoked by `init` function in `index.html`.)
#[wasm_bindgen(start)]
pub fn start() {
    // Mount the `app` to the element with the `id` "app".
    console_error_panic_hook::set_once();
    App::start("app", init, update, view::view);
}
