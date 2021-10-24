/*
Copyright (C) 2020 Kunal Mehta <legoktm@debian.org>

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
use super::codesearch;
use super::{Model, Msg};
use seed::{prelude::*, *};

pub(crate) fn view(model: &Model) -> Node<Msg> {
    div![
        div![
            C!["container"],
            view_heading(model),
            view_form(model),
            IF!(model.error.is_some() => div![
                C!["bg-warning", "text-dark"],
                model.error.as_ref().unwrap()
            ]),
        ],
        div![
            C!["container"],
            IF!(model.results.is_some() => view_response(
                &model.result_format,
                model.hound_config.as_ref().unwrap(),
                model.results.as_ref().unwrap()
            )),
        ]
    ]
}

fn view_heading(model: &Model) -> Node<Msg> {
    // TODO: Move this to server-side to avoid stuff moving after load
    div![
        C!["heading"],
        h2!["MediaWiki code search"],
        ul![codesearch::backends().iter().map(|(backend, label)| {
            let bkend = backend.clone();
            li![
                C!["index"],
                ev(Ev::Click, move |_| { Msg::ChangeProfile(bkend) }),
                if &model.profile == backend {
                    b![label]
                } else {
                    a![label]
                }
            ]
        })]
    ]
}

fn view_form(model: &Model) -> Node<Msg> {
    form![
        div![
            C!["form-row"],
            div![
                C!["form-group col-12 col-sm-10 order-1"],
                input![
                    C!["form-query form-control form-control-lg"],
                    attrs! {
                        At::Type => "text",
                        At::AutoFocus => true,
                        At::Placeholder => "Search query...",
                        At::Value => &model.options.query
                    },
                    input_ev(Ev::Input, Msg::SearchQueryChanged),
                    keyboard_ev(Ev::KeyDown, |keyboard_event| {
                        IF!(keyboard_event.key() == "Enter" => Msg::SearchSubmitted)
                    }),
                ],
            ],
            div![
                C!["form-group col-2 order-last order-sm-2"],
                button![
                    C!["btn btn-primary btn-lg"],
                    attrs! {At::Type => "button"},
                    ev(Ev::Click, |event| {
                        event.prevent_default();
                        Msg::SearchSubmitted
                    }),
                    IF!(model.loading => span![
                        C!["spinner-border spinner-border-sm search-spinner"],
                        attrs!{At::from("role") => "status"},
                    ]),
                    IF!(model.loading => "Searching..."),
                    IF!(!model.loading => "Search!"),
                ]
            ],
            div![
                C!["form-group col-12 col-sm-6 order-3"],
                /*label![
                    attrs! {At::For => "file-path"},
                    "File path"
                ],*/
                input![
                    C!["form-control"],
                    attrs! {
                        At::Id => "file-path",
                        At::Type => "text",
                        At::Placeholder => "File path (regexp)",
                        At::Value => &model.options.files
                    },
                    input_ev(Ev::Input, Msg::FilesChanged),
                    keyboard_ev(Ev::KeyDown, |keyboard_event| {
                        IF!(keyboard_event.key() == "Enter" => Msg::SearchSubmitted)
                    }),
                ],
            ],
            div![
                C!["form-group col-12 col-sm-6 order-4"],
                div![
                    C!["form-check case-insensitive-checkbox"],
                    input![
                        C!["form-check-input"],
                        attrs! {
                            At::Id => "case-insensitive",
                            At::Type => "checkbox",
                            At::Checked => model.options.case_insensitive.as_at_value(),
                        },
                        ev(Ev::Click, |_| Msg::CaseInsensitiveChanged),
                    ],
                    label![
                        C!["form-check-label"],
                        attrs! {At::For => "case-insensitive"},
                        "Ignore case"
                    ],
                ]
            ]
        ],
        IF!(model.results.is_some() => view_form_result_format(model)),
    ]
}

fn view_form_result_format(model: &Model) -> Node<Msg> {
    let formats = vec!["Default", "Phabricator"];
    let selected = &model.result_format;
    div![
        "Result format: ",
        formats.iter().map(|fmt| {
            let id = format!("format-{}", &fmt);
            div![
                C!["form-check", "form-check-inline"],
                input![
                    C!["form-check-input"],
                    attrs! {
                        At::Type => "radio",
                        At::Name => "format",
                        At::Id => &id,
                        At::Value => &fmt,
                        At::Checked => (fmt == selected).as_at_value(),
                    },
                    input_ev(Ev::Input, Msg::ChangeResultFormat)
                ],
                label![C!["form-check-label"], attrs! {At::For => &id}, &fmt]
            ]
        })
    ]
}

fn build_url(
    cfg: &codesearch::RepoConfig,
    rev: &str,
    path: &str,
    lineno: Option<&u32>,
) -> String {
    let anchor = match lineno {
        Some(lineno) => cfg
            .url_pattern
            .anchor
            .replace("{line}", &lineno.to_string()),
        None => "".to_string(),
    };
    cfg.url_pattern
        .base_url
        .replace("{url}", &cfg.url)
        .replace("{rev}", rev)
        .replace("{path}", path)
        .replace("{anchor}", &anchor)
}

fn view_response(
    result_format: &str,
    hound_config: &codesearch::HoundConfig,
    results: &codesearch::HoundResults,
) -> Node<Msg> {
    if results.is_empty() {
        return div![
            C!["alert alert-primary"],
            attrs! {At::from("role") => "alert"},
            "No results found"
        ];
    }
    match result_format {
        "Default" => view_response_default(hound_config, results),
        "Phabricator" => view_response_phabricator(hound_config, results),
        _ => panic!("Unknown result format"),
    }
}

fn view_response_phabricator(
    hound_config: &codesearch::HoundConfig,
    results: &codesearch::HoundResults,
) -> Node<Msg> {
    let mut text: Vec<String> = results
        .iter()
        .map(|(repo, result)| {
            // FIXME: what if config.json and hound get out of sync?
            let cfg = hound_config.get(&repo.to_owned()).unwrap();
            let mut ret = vec![format!(
                "[ ] {} ({} files)",
                repo, result.files_with_match
            )];
            for match_ in &result.matches {
                let num_matches = match_.matches.len();
                let filename = match_.filename.clone();
                let url = build_url(cfg, &result.revision, &filename, None);
                let phab = format!(
                    "** [[{}|{}]] ({} matches)",
                    url, filename, num_matches
                );
                ret.push(phab);
            }
            ret.join("\n")
        })
        .collect();
    text.sort_unstable();
    div![pre![code![text.join("\n")]]]
}

fn view_response_default(
    hound_config: &codesearch::HoundConfig,
    original_results: &codesearch::HoundResults,
) -> Node<Msg> {
    let hresults = original_results.clone();
    let mut results: Vec<(&String, &codesearch::RepoResult)> =
        hresults.iter().collect();
    results.sort_unstable_by(|(a_name, a_res), (b_name, b_res)| {
        if b_res.files_with_match == a_res.files_with_match {
            // Sort in alpha, ascending (A ... Z)
            a_name.partial_cmp(b_name).unwrap()
        } else {
            // Sort numerically, descending (more results ... less results)
            b_res
                .files_with_match
                .partial_cmp(&a_res.files_with_match)
                .unwrap()
        }
    });
    div![
        C!["results row"],
        div![
            C!["cards col-lg"],
            results.iter().map(|(repo, result)| {
                // FIXME: what if config.json and hound get out of sync?
                let cfg = hound_config.get(repo.to_owned()).unwrap();
                let has_more = result.files_with_match > result.matches.len();
                let repo_name = repo.to_owned().clone();
                div![
                    C!["repo"],
                    h2![
                        C!["repo-name"],
                        attrs!{At::Id => repo},
                        repo
                    ],
                    result.matches.iter().map(|match_| {
                        let flat = codesearch::flatten(&match_);
                        let filename = flat.name.clone();
                        div![
                            C!["card file"],
                            div![
                                C!["card-header filename"],
                                a![
                                    attrs! {At::Href => build_url(cfg, &result.revision, &filename, None)},
                                    flat.name
                                ]
                            ],
                            div![
                                C!["card-body lines"],
                                pre![code![
                                    flat.lines.iter().map(|(lineno, line)| {
                                        div![
                                            C!["line"],
                                            span![C!["lineno border-right"],
                                                a![
                                                    attrs!{
                                                        At::Href => build_url(
                                                            cfg,
                                                            &result.revision,
                                                            &filename,
                                                            Some(&lineno)
                                                        )
                                                    },
                                                    // XXX: I'm lazy, just pad to 4 digits so everything
                                                    // lines up
                                                    &format!("{:>4}", lineno)
                                                ]
                                            ],
                                            // hound re runs the regex over every line to highlight just the
                                            // match, that's overkill for now
                                            span![
                                                C!["code", IF!(line.highlight => "highlight")],
                                               &line.text
                                           ]
                                        ]
                                    })
                                ]]
                            ]
                        ]
                    }),
                    IF!(has_more => button![
                        C!["btn btn-secondary load-more"],
                        attrs!{At::Type => "button"},
                        ev(Ev::Click, move |_| {
                            Msg::LoadMoreResults(repo_name)
                        }),
                        format!("Load all {} matches in {}", result.files_with_match, repo),
                    ]),
                ]
            })
        ],
        div![
            C!["reposlist col col-md-auto"],
            h5!["Matched repositories"],
            ul![
                C!["nav flex-column"],
                results.iter().map(|(repo, result)| {
                    li![
                        C!["nav-item"],
                        a![
                            C!["nav-link"],
                            attrs!{At::Href => format!("#{}", repo)},
                            format!("{} ", repo),
                            span![
                                C!["badge badge-secondary"],
                                format!("{}", result.files_with_match)
                            ]
                        ]
                    ]
                })
            ],
        ],
    ]
}
