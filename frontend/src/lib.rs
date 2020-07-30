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
        Url::new()
            .add_path_part(&format!("{}/", self.profile))
            .set_search(UrlSearch::new(vec![
                ("q", vec![&self.options.query]),
                ("i", vec![&case_insenstive]),
                ("files", vec![&self.options.files]),
            ]))
    }
}

/// `Msg` describes the different events you can modify state with.
enum Msg {
    SearchSubmitted,
    SearchQueryChanged(String),
    FilesChanged(String),
    CaseInsensitiveChanged,
    ResultsReceived(codesearch::HoundConfig, codesearch::HoundResults),
    ResultsErrored(String),
    ChangeProfile(String),
    ChangeResultFormat(String),
}

/// `update` describes how to handle each `Msg`.
fn update(msg: Msg, model: &mut Model, orders: &mut impl Orders<Msg>) {
    match msg {
        Msg::SearchSubmitted => {
            model.loading = true;
            model.error = None;
            model.results = None;
            let options = model.options.clone();
            let profile = model.profile.clone();
            orders.perform_cmd(async move {
                let fconfig = codesearch::fetch_config(&profile);
                let fresults = codesearch::send_query(&options, &profile);
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
            util::history()
                .push_state_with_url(
                    &JsValue::from_str("{}"),
                    "",
                    Some(&model.to_url().to_string()),
                )
                .unwrap();
        }
        Msg::SearchQueryChanged(val) => {
            model.options.query = val;
        }
        Msg::FilesChanged(val) => {
            model.options.files = val;
        }
        Msg::CaseInsensitiveChanged => {
            let current = model.options.case_insensitive;
            model.options.case_insensitive = !current;
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
            model.results = None;
        }
        Msg::ChangeResultFormat(result_format) => {
            model.result_format = result_format;
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
