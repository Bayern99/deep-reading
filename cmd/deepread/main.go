// Command deepread is the thin CLI over DeepRead's bundle, view, and export
// packages. Every command prints deterministic JSON on stdout on success and a
// structured JSON error on stderr on failure; the process exit code is the
// branch signal an Agent should use.
package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"strconv"
	"strings"

	"deepread/internal/bundle"
	"deepread/internal/export"
	"deepread/internal/ingest"
	"deepread/internal/view"
)

const cliVersion = "0.3.0"

const usageText = `deepread — prose-preserving deep reading for Markdown articles and EPUB books.
deepread — 为一篇 Markdown 文章或一本 EPUB 电子书生成原文保真的深读页。

Usage / 用法:
  deepread <command> [flags] <doc.md>

Commands (10) / 命令:
  ingest   <src.md|book.epub> -o <out-dir>
           [--lang <bcp47>] [--source-lang <bcp47>] [--mode original|translated|bilingual]
      Import a Markdown file or EPUB into a new document bundle directory.
      将一个 Markdown 文件或 EPUB 导入新的文档包目录。

  inspect  <doc.md> [--heading <text> [--occurrence <n>]] [--lines <start>:<end>]
      Report bundle state (revision, viewHash, reader contract, translation
      coverage, sections, open notes) and an optional excerpt.

  prepare  <doc.md> --breaks <file|->
      Insert synthetic H2 anchors (JSON array of {beforeLine, title}).

  catalog  [--profile canvas|margin]
      Print the reading contract: the full 50-component canvas (default) or the
      legacy 10-primitive margin subset.

  blocks   <doc.md>
      List the translatable blocks (id, kind, sourceHash, text) of the document.

  write    <doc.md> --statements <file|-> [--source id=<Heading>[#<occ>]]...
           [--cite <stmt>:<srcId>=<blockId>[,<blockId>...]]...
           [--profile canvas|margin] [--model <m>] [--request <r>]
      Commit a validated GenUI view revision.

  translate <doc.md> --lang <bcp47> --input <file|->
            [--mode translated|bilingual] [--source-lang <bcp47>]
      Merge translated blocks (JSON array, {"entries":[...]}, or JSONL) into the
      parallel translation layer and record the reading contract.

  note add <doc.md> (--node <stmt> [--source <srcId>] | --heading <h> [--occurrence <n>])
           --text <note> [--rev <r>] [--msg-id <id>]
      Record a reader note; a repeated --msg-id is idempotent.

  patch    <doc.md> --replace <stmt> [--replace <stmt2>] --expect-hash <sha256>
           [--expect-source-hash <srcId>=<hash>]... --statements <file|->
           [--source id=<Heading>[#<occ>]]...
           [--cite <stmt>:<srcId>=<blockId>[,<blockId>...]]...
           [--resolve-note <id>]... [--profile canvas|margin]
           [--model <m>] [--request <r>]
      Replace selected top-level Source modules with compare-and-swap.

  export   <doc.md> -o <out.html> [flags]
  export   <doc1.md> <doc2.md> ... -o <out.html> [--title <t>] [flags]
  export   --book <book-dir> [--chapters <spec>] -o <out.html> [--title <t>] [flags]
      Render one unified offline reader page (single doc, chapter list, or book).
      Flags: --face inline|dual|genui|read|margin  --lang auto|original|<bcp47>
             --mode auto|original|translated|bilingual  --no-js
             --allow-partial-translation  --external-assets
             --max-bytes <n>  --max-image-bytes <n>

Global / 全局:
  --help, -h    Show this help / 显示帮助.
  --version     Print the version / 显示版本.

Flags may appear before or after <doc.md>; -- stops flag parsing.
标志可放在 <doc.md> 前后；使用 -- 结束标志解析。

Exit codes / 退出码:
  0 success | 1 runtime error | 2 usage error
  3 validation rejection, unsafe asset, or incomplete translation
  4 not found | 5 hash or revision conflict
  0 成功 | 1 运行错误 | 2 用法错误
  3 校验拒绝、不安全资产或翻译未完成
  4 未找到 | 5 哈希或版本冲突
`

func main() {
	os.Exit(run(os.Stdin, os.Args[1:], os.Stdout, os.Stderr))
}

// run drives the whole CLI in-process so integration tests need no subprocess.
func run(stdin io.Reader, argv []string, stdout, stderr io.Writer) int {
	if err := execute(stdin, argv, stdout); err != nil {
		return writeError(stderr, err)
	}
	return 0
}

// usageError marks a malformed invocation (exit code 2).
type usageError struct {
	message string
}

func (e *usageError) Error() string { return e.message }

// rejectionError is a structured exit-3 rejection raised by the CLI itself
// (an incomplete translation batch) rather than by the view package.
type rejectionError struct {
	code    string
	message string
	hint    string
}

func (e *rejectionError) Error() string { return e.message }

func execute(stdin io.Reader, argv []string, stdout io.Writer) error {
	if len(argv) == 0 {
		return &usageError{message: "missing command; run `deepread help`"}
	}
	switch argv[0] {
	case "help", "--help", "-h":
		fmt.Fprint(stdout, usageText)
		return nil
	case "version", "--version", "-v":
		fmt.Fprintln(stdout, "deepread "+cliVersion)
		return nil
	}

	command, args := argv[0], argv[1:]
	switch command {
	case "ingest":
		return runIngest(args, stdout)
	case "prepare":
		return runPrepare(stdin, args, stdout)
	case "inspect":
		return runInspect(args, stdout)
	case "catalog":
		return runCatalog(args, stdout)
	case "blocks":
		return runBlocks(args, stdout)
	case "write":
		return runWrite(stdin, args, stdout)
	case "translate":
		return runTranslate(stdin, args, stdout)
	case "note":
		return runNote(stdin, args, stdout)
	case "patch":
		return runPatch(stdin, args, stdout)
	case "export":
		return runExport(args, stdout)
	default:
		return &usageError{message: fmt.Sprintf("unknown command %q; run `deepread help`", command)}
	}
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

func runIngest(args []string, stdout io.Writer) error {
	fl, err := parseFlags(args, map[string]flagKind{
		"out":         flagString,
		"lang":        flagString,
		"source-lang": flagString,
		"mode":        flagString,
		"help":        flagBool,
	})
	if err != nil {
		return err
	}
	if fl.bool("help") {
		fmt.Fprint(stdout, usageText)
		return nil
	}
	srcPath, err := fl.singleArg("<src.md|book.epub>")
	if err != nil {
		return err
	}
	outDir, err := fl.required("out")
	if err != nil {
		return err
	}
	contract, err := readingContract(fl)
	if err != nil {
		return err
	}
	result, err := ingest.Ingest(srcPath, outDir, ingest.Options{
		SourceLang: contract.SourceLang,
		TargetLang: contract.TargetLang,
		Mode:       contract.Mode,
	})
	if err != nil {
		return err
	}
	return writeJSON(stdout, result)
}

// readingContract validates the --lang/--source-lang/--mode triple and applies
// the v0.3 defaults: naming a target language implies translated reading unless
// it equals the source language (then the document stays original).
func readingContract(fl *flagSet) (bundle.ReaderConfig, error) {
	var cfg bundle.ReaderConfig
	mode := strings.TrimSpace(fl.str("mode"))
	if err := bundle.ValidateReadMode(mode); err != nil {
		return cfg, &usageError{message: err.Error()}
	}
	if raw := fl.str("source-lang"); strings.TrimSpace(raw) != "" {
		canon, err := bundle.CanonicalLang(raw)
		if err != nil {
			return cfg, &usageError{message: err.Error()}
		}
		cfg.SourceLang = canon
	}
	target := ""
	if raw := fl.str("lang"); strings.TrimSpace(raw) != "" {
		canon, err := bundle.CanonicalLang(raw)
		if err != nil {
			return cfg, &usageError{message: err.Error()}
		}
		target = canon
	}
	if mode == "" && target != "" {
		if cfg.SourceLang != "" && cfg.SourceLang == target {
			mode = bundle.ReadModeOriginal
		} else {
			mode = bundle.ReadModeTranslated
		}
	}
	if mode == bundle.ReadModeTranslated || mode == bundle.ReadModeBilingual {
		if target == "" {
			return cfg, &usageError{message: fmt.Sprintf("--mode %s requires --lang <bcp47>", mode)}
		}
	}
	if mode == bundle.ReadModeOriginal {
		// Keep an explicit original contract free of a target-language claim.
		target = ""
	}
	cfg.TargetLang = target
	cfg.Mode = mode
	return cfg, nil
}

func runPrepare(stdin io.Reader, args []string, stdout io.Writer) error {
	fl, err := parseFlags(args, map[string]flagKind{
		"breaks": flagString,
		"help":   flagBool,
	})
	if err != nil {
		return err
	}
	if fl.bool("help") {
		fmt.Fprint(stdout, usageText)
		return nil
	}
	docPath, err := fl.singleDoc()
	if err != nil {
		return err
	}
	breaksPath, err := fl.required("breaks")
	if err != nil {
		return err
	}
	raw, err := readInput(stdin, breaksPath)
	if err != nil {
		return err
	}
	var breaks []bundle.BreakSpec
	if err := json.Unmarshal(raw, &breaks); err != nil {
		return &usageError{message: fmt.Sprintf("--breaks must be a JSON array of {\"beforeLine\", \"title\"} objects: %v", err)}
	}
	result, err := bundle.Prepare(docPath, breaks)
	if err != nil {
		return err
	}
	return writeJSON(stdout, result)
}

func runInspect(args []string, stdout io.Writer) error {
	fl, err := parseFlags(args, map[string]flagKind{
		"heading":    flagString,
		"occurrence": flagInt,
		"lines":      flagString,
		"help":       flagBool,
	})
	if err != nil {
		return err
	}
	if fl.bool("help") {
		fmt.Fprint(stdout, usageText)
		return nil
	}
	docPath, err := fl.singleDoc()
	if err != nil {
		return err
	}
	opts := bundle.InspectOptions{
		Heading:    fl.str("heading"),
		Occurrence: fl.intOr("occurrence", 0),
	}
	if lines := fl.str("lines"); lines != "" {
		start, end, err := parseLineRange(lines)
		if err != nil {
			return err
		}
		opts.StartLine, opts.EndLine = start, end
	}
	report, err := bundle.Inspect(docPath, opts)
	if err != nil {
		return err
	}
	return writeJSON(stdout, report)
}

func runCatalog(args []string, stdout io.Writer) error {
	fl, err := parseFlags(args, map[string]flagKind{
		"profile": flagString,
		"help":    flagBool,
	})
	if err != nil {
		return err
	}
	if fl.bool("help") {
		fmt.Fprint(stdout, usageText)
		return nil
	}
	if len(fl.pos) > 0 {
		return &usageError{message: fmt.Sprintf("catalog takes no arguments, got %q", fl.pos[0])}
	}
	profile := fl.str("profile")
	if strings.TrimSpace(profile) == "" {
		profile = bundle.ProfileCanvas
	}
	text, err := view.CatalogTextFor(profile)
	if err != nil {
		return &usageError{message: err.Error()}
	}
	_, err = io.WriteString(stdout, text)
	return err
}

// blocksReport is the JSON payload of `deepread blocks`.
type blocksReport struct {
	DocPath     string         `json:"docPath"`
	BundleID    string         `json:"bundleId"`
	TotalBlocks int            `json:"totalBlocks"`
	Blocks      []bundle.Block `json:"blocks"`
}

func runBlocks(args []string, stdout io.Writer) error {
	fl, err := parseFlags(args, map[string]flagKind{
		"help": flagBool,
	})
	if err != nil {
		return err
	}
	if fl.bool("help") {
		fmt.Fprint(stdout, usageText)
		return nil
	}
	docPath, err := fl.singleDoc()
	if err != nil {
		return err
	}
	blocks, manifest, err := bundle.ExtractBlocksFromDoc(docPath)
	if err != nil {
		return err
	}
	if blocks == nil {
		blocks = []bundle.Block{}
	}
	return writeJSON(stdout, blocksReport{
		DocPath:     docPath,
		BundleID:    manifest.BundleID,
		TotalBlocks: len(blocks),
		Blocks:      blocks,
	})
}

func runWrite(stdin io.Reader, args []string, stdout io.Writer) error {
	fl, err := parseFlags(args, map[string]flagKind{
		"statements": flagString,
		"source":     flagSlice,
		"cite":       flagSlice,
		"profile":    flagString,
		"model":      flagString,
		"request":    flagString,
		"help":       flagBool,
	})
	if err != nil {
		return err
	}
	if fl.bool("help") {
		fmt.Fprint(stdout, usageText)
		return nil
	}
	docPath, err := fl.singleDoc()
	if err != nil {
		return err
	}
	statementsPath, err := fl.required("statements")
	if err != nil {
		return err
	}
	sources, err := parseSources(fl.list("source"))
	if err != nil {
		return err
	}
	citations, err := parseCitations(fl.list("cite"))
	if err != nil {
		return err
	}
	if citations, err = mergeCitations(docPath, citations); err != nil {
		return err
	}
	statements, err := readInput(stdin, statementsPath)
	if err != nil {
		return err
	}
	result, err := view.Write(docPath, view.WriteOptions{
		StatementsText: string(statements),
		Sources:        sources,
		Profile:        fl.str("profile"),
		Citations:      citations,
		Model:          fl.str("model"),
		Request:        fl.str("request"),
	})
	if err != nil {
		return err
	}
	return writeJSON(stdout, result)
}

func runTranslate(stdin io.Reader, args []string, stdout io.Writer) error {
	fl, err := parseFlags(args, map[string]flagKind{
		"lang":        flagString,
		"input":       flagString,
		"mode":        flagString,
		"source-lang": flagString,
		"help":        flagBool,
	})
	if err != nil {
		return err
	}
	if fl.bool("help") {
		fmt.Fprint(stdout, usageText)
		return nil
	}
	docPath, err := fl.singleDoc()
	if err != nil {
		return err
	}
	lang, err := fl.required("lang")
	if err != nil {
		return err
	}
	canon, err := bundle.CanonicalLang(lang)
	if err != nil {
		return &usageError{message: err.Error()}
	}
	rawLang, err := fl.required("input")
	if err != nil {
		return err
	}
	raw, err := readInput(stdin, rawLang)
	if err != nil {
		return err
	}
	entries, err := parseTranslationEntries(raw)
	if err != nil {
		return err
	}
	status, err := bundle.ApplyTranslations(docPath, canon, entries)
	if err != nil {
		return translateError(err)
	}
	if err := persistReaderConfig(docPath, canon, fl); err != nil {
		return err
	}
	return writeJSON(stdout, status)
}

// translateError keeps the CLI-level meaning of every ApplyTranslations failure:
// hash conflicts stay conflicts, unsafe/unknown content is a validation
// rejection, and a missing document stays "not found".
func translateError(err error) error {
	switch {
	case errors.Is(err, bundle.ErrConflict), errors.Is(err, bundle.ErrInvalidLang), errors.Is(err, fs.ErrNotExist):
		return err
	}
	return &rejectionError{
		code:    "VALIDATION_FAILED",
		message: err.Error(),
		hint:    "Send one entry per live block id from `deepread blocks`, with its exact sourceHash and non-empty translated text (no raw <script>, no block-level images).",
	}
}

// persistReaderConfig records the reading contract so `inspect` and
// `export --lang auto --mode auto` agree with the translation layer.
func persistReaderConfig(docPath, canon string, fl *flagSet) error {
	docBytes, err := os.ReadFile(docPath)
	if err != nil {
		return err
	}
	manifest, _, err := bundle.LoadManifest(docPath, docBytes)
	if err != nil {
		return err
	}
	cfg := bundle.ReaderConfig{}
	explicit := false
	if manifest.Reader != nil {
		cfg = *manifest.Reader
	}
	if raw := fl.str("source-lang"); strings.TrimSpace(raw) != "" {
		cfg.SourceLang = strings.TrimSpace(raw)
		explicit = true
	}
	if raw := strings.TrimSpace(fl.str("mode")); raw != "" {
		if err := bundle.ValidateReadMode(raw); err != nil {
			return &usageError{message: err.Error()}
		}
		cfg.Mode = raw
		explicit = true
	}
	if cfg.TargetLang == "" {
		cfg.TargetLang = canon
		explicit = true
	}
	if cfg.Mode == "" {
		if cfg.SourceLang != "" && cfg.SourceLang == canon {
			cfg.Mode = bundle.ReadModeOriginal
		} else {
			cfg.Mode = bundle.ReadModeTranslated
		}
		explicit = true
	}
	if !explicit {
		return nil
	}
	if err := bundle.SetReaderConfig(docPath, cfg); err != nil {
		if errors.Is(err, bundle.ErrInvalidLang) {
			return &usageError{message: err.Error()}
		}
		return err
	}
	return nil
}

// parseTranslationEntries accepts the three shapes an Agent can emit: a JSON
// array, an object with an "entries" array, or JSONL (one object per line).
func parseTranslationEntries(raw []byte) ([]bundle.TranslationEntry, error) {
	trimmed := strings.TrimSpace(string(raw))
	if trimmed == "" {
		return nil, &usageError{message: "--input contains no translation entries"}
	}
	malformed := &usageError{message: `--input must be a JSON array of {"id","sourceHash","text"}, an object {"entries":[...]}, or JSONL with one such object per line`}
	switch trimmed[0] {
	case '[':
		var entries []bundle.TranslationEntry
		if err := json.Unmarshal([]byte(trimmed), &entries); err != nil {
			return nil, &usageError{message: fmt.Sprintf("parse --input JSON array: %v", err)}
		}
		if len(entries) == 0 {
			return nil, malformed
		}
		return entries, nil
	case '{':
		var wrapper struct {
			Entries []bundle.TranslationEntry `json:"entries"`
		}
		if err := json.Unmarshal([]byte(trimmed), &wrapper); err == nil && wrapper.Entries != nil {
			if len(wrapper.Entries) == 0 {
				return nil, malformed
			}
			return wrapper.Entries, nil
		}
		var entries []bundle.TranslationEntry
		for _, line := range strings.Split(trimmed, "\n") {
			line = strings.TrimSpace(line)
			if line == "" {
				continue
			}
			var entry bundle.TranslationEntry
			if err := json.Unmarshal([]byte(line), &entry); err != nil {
				return nil, &usageError{message: fmt.Sprintf("parse --input JSONL line %q: %v", line, err)}
			}
			entries = append(entries, entry)
		}
		if len(entries) == 0 {
			return nil, malformed
		}
		return entries, nil
	default:
		return nil, malformed
	}
}

func runNote(stdin io.Reader, args []string, stdout io.Writer) error {
	if len(args) == 0 {
		return &usageError{message: "note requires a subcommand: `note add`"}
	}
	switch args[0] {
	case "add":
		return runNoteAdd(stdin, args[1:], stdout)
	case "help", "--help", "-h":
		fmt.Fprint(stdout, usageText)
		return nil
	default:
		return &usageError{message: fmt.Sprintf("unknown note subcommand %q; expected `note add`", args[0])}
	}
}

func runNoteAdd(stdin io.Reader, args []string, stdout io.Writer) error {
	fl, err := parseFlags(args, map[string]flagKind{
		"node":       flagString,
		"heading":    flagString,
		"occurrence": flagInt,
		"source":     flagString,
		"text":       flagString,
		"rev":        flagInt,
		"msg-id":     flagString,
		"help":       flagBool,
	})
	if err != nil {
		return err
	}
	if fl.bool("help") {
		fmt.Fprint(stdout, usageText)
		return nil
	}
	docPath, err := fl.singleDoc()
	if err != nil {
		return err
	}
	node := fl.str("node")
	heading := fl.str("heading")
	if (node == "") == (heading == "") {
		return &usageError{message: "note add requires exactly one target: --node <stmt> or --heading <h>"}
	}
	text, err := fl.required("text")
	if err != nil {
		return err
	}
	result, err := bundle.AddNote(docPath, bundle.AddNoteOptions{
		Node:       node,
		Heading:    heading,
		Occurrence: fl.intOr("occurrence", 0),
		SourceID:   fl.str("source"),
		Text:       text,
		BaseRev:    fl.intOr("rev", 0),
		MsgID:      fl.str("msg-id"),
	})
	if err != nil {
		return err
	}
	return writeJSON(stdout, result)
}

func runPatch(stdin io.Reader, args []string, stdout io.Writer) error {
	fl, err := parseFlags(args, map[string]flagKind{
		"replace":            flagCommaSlice,
		"expect-hash":        flagString,
		"expect-source-hash": flagSlice,
		"statements":         flagString,
		"source":             flagSlice,
		"cite":               flagSlice,
		"resolve-note":       flagCommaSlice,
		"profile":            flagString,
		"model":              flagString,
		"request":            flagString,
		"help":               flagBool,
	})
	if err != nil {
		return err
	}
	if fl.bool("help") {
		fmt.Fprint(stdout, usageText)
		return nil
	}
	docPath, err := fl.singleDoc()
	if err != nil {
		return err
	}
	replace := fl.list("replace")
	if len(replace) == 0 {
		return &usageError{message: "patch requires at least one --replace <stmt>"}
	}
	expectHash, err := fl.required("expect-hash")
	if err != nil {
		return err
	}
	statementsPath, err := fl.required("statements")
	if err != nil {
		return err
	}
	sources, err := parseSources(fl.list("source"))
	if err != nil {
		return err
	}
	citations, err := parseCitations(fl.list("cite"))
	if err != nil {
		return err
	}
	if citations, err = mergeCitations(docPath, citations); err != nil {
		return err
	}
	expectSourceHashes, err := parseSourceHashes(fl.list("expect-source-hash"))
	if err != nil {
		return err
	}
	statements, err := readInput(stdin, statementsPath)
	if err != nil {
		return err
	}
	result, err := view.Patch(docPath, view.PatchOptions{
		Replace:            replace,
		ExpectHash:         expectHash,
		ExpectSourceHashes: expectSourceHashes,
		StatementsText:     string(statements),
		AddedSources:       sources,
		ResolveNotes:       fl.list("resolve-note"),
		Profile:            fl.str("profile"),
		Citations:          citations,
		Model:              fl.str("model"),
		Request:            fl.str("request"),
	})
	if err != nil {
		return err
	}
	return writeJSON(stdout, result)
}

func runExport(args []string, stdout io.Writer) error {
	fl, err := parseFlags(args, map[string]flagKind{
		"out":                       flagString,
		"title":                     flagString,
		"face":                      flagString,
		"lang":                      flagString,
		"mode":                      flagString,
		"book":                      flagString,
		"chapters":                  flagCommaSlice,
		"no-js":                     flagBool,
		"allow-partial-translation": flagBool,
		"external-assets":           flagBool,
		"max-bytes":                 flagInt,
		"max-image-bytes":           flagInt,
		"help":                      flagBool,
	})
	if err != nil {
		return err
	}
	if fl.bool("help") {
		fmt.Fprint(stdout, usageText)
		return nil
	}
	outPath, err := fl.required("out")
	if err != nil {
		return err
	}
	bookDir := strings.TrimSpace(fl.str("book"))
	chapters := fl.list("chapters")
	if bookDir == "" {
		if len(chapters) > 0 {
			return &usageError{message: "--chapters requires --book <book-dir>"}
		}
		if len(fl.pos) == 0 {
			return &usageError{message: "missing <doc.md> argument (or pass --book <book-dir>)"}
		}
	} else if len(fl.pos) > 0 {
		return &usageError{message: fmt.Sprintf("--book does not take positional documents, got %q", fl.pos[0])}
	}

	opts := export.ExportOptions{
		Title:                   fl.str("title"),
		Face:                    strings.TrimSpace(fl.str("face")),
		NoJS:                    fl.bool("no-js"),
		AllowPartialTranslation: fl.bool("allow-partial-translation"),
		ExternalAssets:          fl.bool("external-assets"),
	}
	switch opts.Face {
	case "", "inline", "hybrid", "dual", "genui", "read", "margin":
	default:
		return &usageError{message: fmt.Sprintf("invalid --face %q (expected inline, hybrid, dual, genui, read, or margin)", opts.Face)}
	}
	lang := strings.TrimSpace(fl.str("lang"))
	if lang != "" && !strings.EqualFold(lang, "auto") && !strings.EqualFold(lang, "original") {
		canon, err := bundle.CanonicalLang(lang)
		if err != nil {
			return &usageError{message: err.Error()}
		}
		lang = canon
	}
	opts.Lang = lang
	mode := strings.TrimSpace(fl.str("mode"))
	if mode != "" && !strings.EqualFold(mode, "auto") {
		if err := bundle.ValidateReadMode(mode); err != nil {
			return &usageError{message: err.Error()}
		}
	}
	opts.Mode = mode
	for _, limit := range []struct {
		name   string
		target *int
	}{
		{name: "max-bytes", target: &opts.MaxHTMLBytes},
		{name: "max-image-bytes", target: &opts.MaxImageBytes},
	} {
		raw := strings.TrimSpace(fl.str(limit.name))
		if raw == "" {
			continue
		}
		value, err := strconv.Atoi(raw)
		if err != nil || value <= 0 {
			return &usageError{message: fmt.Sprintf("--%s must be a positive integer, got %q", limit.name, raw)}
		}
		*limit.target = value
	}

	var result export.ExportResult
	var exportErr error
	switch {
	case bookDir != "":
		result, exportErr = export.ExportBook(bookDir, chapters, outPath, opts)
	case len(fl.pos) == 1:
		result, exportErr = export.Export(fl.pos[0], outPath, opts)
	default:
		result, exportErr = export.ExportChapters(fl.pos, opts.Title, outPath, opts)
	}
	if exportErr != nil {
		return exportErr
	}
	return writeJSON(stdout, result)
}

// ---------------------------------------------------------------------------
// Flag parsing
// ---------------------------------------------------------------------------

type flagKind int

const (
	flagString flagKind = iota
	flagInt
	flagSlice
	flagCommaSlice
	flagBool
)

// flagAliases maps short forms onto their canonical flag name.
var flagAliases = map[string]string{
	"o": "out",
}

type flagSet struct {
	values   map[string][]string
	switches map[string]bool
	pos      []string
}

// parseFlags interleaves flags with positional arguments, supports `--name
// value`, `--name=value`, a lone `-` as a stdin value, and `--` as an explicit
// end of flags.
func parseFlags(args []string, specs map[string]flagKind) (*flagSet, error) {
	fl := &flagSet{values: map[string][]string{}, switches: map[string]bool{}}
	for i := 0; i < len(args); i++ {
		arg := args[i]
		if arg == "--" {
			fl.pos = append(fl.pos, args[i+1:]...)
			return fl, nil
		}
		if arg == "-" || !strings.HasPrefix(arg, "-") {
			fl.pos = append(fl.pos, arg)
			continue
		}
		name := strings.TrimLeft(arg, "-")
		if name == "" {
			fl.pos = append(fl.pos, arg)
			continue
		}
		value, hasValue := "", false
		if eq := strings.IndexByte(name, '='); eq >= 0 {
			value, hasValue = name[eq+1:], true
			name = name[:eq]
		}
		if alias, ok := flagAliases[name]; ok {
			name = alias
		}
		kind, known := specs[name]
		if !known {
			return nil, &usageError{message: fmt.Sprintf("unknown flag %q", arg)}
		}
		if kind == flagBool {
			if !hasValue {
				fl.switches[name] = true
				continue
			}
			switch strings.ToLower(value) {
			case "true", "1", "yes":
				fl.switches[name] = true
			case "false", "0", "no":
				fl.switches[name] = false
			default:
				return nil, &usageError{message: fmt.Sprintf("flag --%s expects a boolean value", name)}
			}
			continue
		}
		if !hasValue {
			if i+1 >= len(args) {
				return nil, &usageError{message: fmt.Sprintf("flag --%s requires a value", name)}
			}
			next := args[i+1]
			if next != "-" && strings.HasPrefix(next, "--") {
				return nil, &usageError{message: fmt.Sprintf("flag --%s requires a value", name)}
			}
			value = next
			i++
		}
		switch kind {
		case flagInt:
			trimmed := strings.TrimSpace(value)
			if _, err := strconv.Atoi(trimmed); err != nil {
				return nil, &usageError{message: fmt.Sprintf("flag --%s expects an integer, got %q", name, value)}
			}
			fl.values[name] = append(fl.values[name], trimmed)
		case flagCommaSlice:
			for _, part := range strings.Split(value, ",") {
				if part = strings.TrimSpace(part); part != "" {
					fl.values[name] = append(fl.values[name], part)
				}
			}
		default:
			fl.values[name] = append(fl.values[name], value)
		}
	}
	return fl, nil
}

func (f *flagSet) str(name string) string {
	values := f.values[name]
	if len(values) == 0 {
		return ""
	}
	return values[len(values)-1]
}

func (f *flagSet) list(name string) []string { return f.values[name] }

func (f *flagSet) bool(name string) bool { return f.switches[name] }

func (f *flagSet) intOr(name string, fallback int) int {
	raw := f.str(name)
	if raw == "" {
		return fallback
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		return fallback
	}
	return value
}

func (f *flagSet) required(name string) (string, error) {
	value := f.str(name)
	if strings.TrimSpace(value) == "" {
		return "", &usageError{message: fmt.Sprintf("missing required flag --%s", name)}
	}
	return value, nil
}

func (f *flagSet) singleDoc() (string, error) { return f.singleArg("<doc.md>") }

// singleArg requires exactly one positional argument and names the expected
// placeholder in the error so the message matches the command's usage line.
func (f *flagSet) singleArg(placeholder string) (string, error) {
	if len(f.pos) == 0 {
		return "", &usageError{message: "missing " + placeholder + " argument"}
	}
	if len(f.pos) > 1 {
		return "", &usageError{message: fmt.Sprintf("unexpected argument %q", f.pos[1])}
	}
	return f.pos[0], nil
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func parseSourceHashes(specs []string) (map[string]string, error) {
	if len(specs) == 0 {
		return nil, nil
	}
	hashes := make(map[string]string, len(specs))
	for _, spec := range specs {
		eq := strings.IndexByte(spec, '=')
		if eq <= 0 || eq == len(spec)-1 {
			return nil, &usageError{message: fmt.Sprintf("invalid --expect-source-hash %q: expected <sourceId>=<hash>", spec)}
		}
		id := strings.TrimSpace(spec[:eq])
		h := strings.TrimSpace(spec[eq+1:])
		if id == "" || h == "" {
			return nil, &usageError{message: fmt.Sprintf("invalid --expect-source-hash %q: expected <sourceId>=<hash>", spec)}
		}
		hashes[id] = h
	}
	return hashes, nil
}

func parseSources(specs []string) (map[string]view.SourceRef, error) {
	sources := make(map[string]view.SourceRef, len(specs))
	for _, spec := range specs {
		id, ref, err := view.ParseSourceFlag(spec)
		if err != nil {
			return nil, &usageError{message: err.Error()}
		}
		if _, duplicate := sources[id]; duplicate {
			return nil, &usageError{message: fmt.Sprintf("source id %q is mapped more than once", id)}
		}
		sources[id] = ref
	}
	return sources, nil
}

// parseCitations parses `--cite <statement>:<sourceId>=<blockId>[,<blockId>...]`
// into the citation map persisted beside the view.
func parseCitations(specs []string) (bundle.CitationMap, error) {
	if len(specs) == 0 {
		return nil, nil
	}
	citations := bundle.CitationMap{}
	for _, spec := range specs {
		shape := "expected <statement>:<sourceId>=<blockId>[,<blockId>...]"
		colon := strings.IndexByte(spec, ':')
		if colon <= 0 {
			return nil, &usageError{message: fmt.Sprintf("invalid --cite %q: %s", spec, shape)}
		}
		statement := strings.TrimSpace(spec[:colon])
		rest := spec[colon+1:]
		eq := strings.IndexByte(rest, '=')
		if statement == "" || eq <= 0 || eq == len(rest)-1 {
			return nil, &usageError{message: fmt.Sprintf("invalid --cite %q: %s", spec, shape)}
		}
		sourceID := strings.TrimSpace(rest[:eq])
		var blockIDs []string
		for _, part := range strings.Split(rest[eq+1:], ",") {
			if part = strings.TrimSpace(part); part != "" {
				blockIDs = append(blockIDs, part)
			}
		}
		if sourceID == "" || len(blockIDs) == 0 {
			return nil, &usageError{message: fmt.Sprintf("invalid --cite %q: %s", spec, shape)}
		}
		if citations[statement] == nil {
			citations[statement] = map[string][]string{}
		}
		citations[statement][sourceID] = append(citations[statement][sourceID], blockIDs...)
	}
	return citations, nil
}

// mergeCitations overlays new --cite anchors onto the citations already stored
// for the bundle, so editing one module never strips another module's
// 查看原文 anchors.
func mergeCitations(docPath string, provided bundle.CitationMap) (bundle.CitationMap, error) {
	if provided == nil {
		return nil, nil
	}
	existing, err := bundle.LoadCitations(docPath)
	if err != nil {
		return nil, err
	}
	if len(existing) == 0 {
		return provided, nil
	}
	merged := bundle.CitationMap{}
	for statement, sources := range existing {
		copied := make(map[string][]string, len(sources))
		for sourceID, blockIDs := range sources {
			copied[sourceID] = blockIDs
		}
		merged[statement] = copied
	}
	for statement, sources := range provided {
		if merged[statement] == nil {
			merged[statement] = map[string][]string{}
		}
		for sourceID, blockIDs := range sources {
			merged[statement][sourceID] = blockIDs
		}
	}
	return merged, nil
}

func parseLineRange(raw string) (int, int, error) {
	parts := strings.Split(raw, ":")
	if len(parts) != 2 {
		return 0, 0, &usageError{message: fmt.Sprintf("--lines expects <start>:<end>, got %q", raw)}
	}
	start, err := strconv.Atoi(strings.TrimSpace(parts[0]))
	if err != nil || start < 1 {
		return 0, 0, &usageError{message: fmt.Sprintf("--lines start must be a positive integer, got %q", parts[0])}
	}
	end, err := strconv.Atoi(strings.TrimSpace(parts[1]))
	if err != nil || end < 1 {
		return 0, 0, &usageError{message: fmt.Sprintf("--lines end must be a positive integer, got %q", parts[1])}
	}
	return start, end, nil
}

// readInput reads a file argument, or all of stdin when the argument is "-".
func readInput(stdin io.Reader, path string) ([]byte, error) {
	if path == "-" {
		data, err := io.ReadAll(stdin)
		if err != nil {
			return nil, fmt.Errorf("read stdin: %w", err)
		}
		return data, nil
	}
	return os.ReadFile(path)
}

func writeJSON(w io.Writer, value any) error {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	_, err = w.Write(append(data, '\n'))
	return err
}

type errorBody struct {
	Code      string `json:"code"`
	Statement string `json:"statement,omitempty"`
	Path      string `json:"path,omitempty"`
	Message   string `json:"message"`
	Hint      string `json:"hint,omitempty"`
}

type errorEnvelope struct {
	Error errorBody `json:"error"`
}

// writeError emits the structured error JSON on stderr and returns the stable
// exit code for its class.
func writeError(w io.Writer, err error) int {
	var usage *usageError
	var invalid *view.ValidationError
	var rejection *rejectionError

	body := errorBody{}
	code := 1
	switch {
	case errors.As(err, &usage):
		code = 2
		body = errorBody{Code: "INVALID_ARGS", Message: usage.message}
	case errors.As(err, &invalid):
		code = 3
		body = errorBody{
			Code:      invalid.Code,
			Statement: invalid.Statement,
			Path:      invalid.Path,
			Message:   invalid.Message,
			Hint:      invalid.Hint,
		}
	case errors.As(err, &rejection):
		code = 3
		body = errorBody{Code: rejection.code, Message: rejection.message, Hint: rejection.hint}
	case errors.Is(err, bundle.ErrTranslationIncomplete):
		code = 3
		body = errorBody{
			Code:    "TRANSLATION_INCOMPLETE",
			Message: err.Error(),
			Hint:    "Run `deepread blocks` for every live block id, translate all of them (missing and stale ids are listed above), then `deepread translate` and export again.",
		}
	case errors.Is(err, ingest.ErrUnsupportedFormat):
		code = 2
		body = errorBody{
			Code:    "INVALID_ARGS",
			Message: err.Error(),
			Hint:    "Supported ingest formats: .md, .markdown, .epub.",
		}
	case errors.Is(err, bundle.ErrInvalidLang):
		code = 2
		body = errorBody{
			Code:    "INVALID_ARGS",
			Message: err.Error(),
			Hint:    "Pass a BCP 47 tag such as zh-CN, en, ja, or pt-BR.",
		}
	case errors.Is(err, export.ErrAssetBudgetExceeded):
		code = 3
		body = errorBody{
			Code:    "ASSET_BUDGET_EXCEEDED",
			Message: err.Error(),
			Hint:    "Re-run export with --external-assets for HTTPS directory hosting or compress large images.",
		}
	case errors.Is(err, export.ErrUnsafeAssetPath):
		code = 3
		body = errorBody{
			Code:    "UNSAFE_ASSET_PATH",
			Message: err.Error(),
			Hint:    "Reference only safe raster images (PNG/JPEG/GIF/WebP/AVIF) inside the document directory.",
		}
	case errors.Is(err, ingest.ErrUnsafeArchive):
		code = 3
		body = errorBody{
			Code:    "UNSAFE_ARCHIVE",
			Message: err.Error(),
			Hint:    "Remove path traversal, symlink escapes, or non-raster assets from the input.",
		}
	case errors.Is(err, ingest.ErrArchiveLimit):
		code = 3
		body = errorBody{
			Code:    "ARCHIVE_LIMIT_EXCEEDED",
			Message: err.Error(),
			Hint:    "Input archive exceeds safety limits (max entries, per-file size, or total decompressed bytes).",
		}
	case errors.Is(err, view.ErrHashConflict) || errors.Is(err, bundle.ErrStaleRevision) ||
		errors.Is(err, bundle.ErrDocMismatch) || errors.Is(err, bundle.ErrConflict):
		code = 5
		body = errorBody{
			Code:    "CONFLICT",
			Message: err.Error(),
			Hint:    "Run deepread inspect to fetch the latest revision, viewHash, and live block hashes before retrying (use one directory per document).",
		}
	case errors.Is(err, fs.ErrNotExist) || errors.Is(err, bundle.ErrNotFound):
		code = 4
		body = errorBody{Code: "NOT_FOUND", Message: err.Error()}
	default:
		code = 1
		body = errorBody{Code: "RUNTIME_ERROR", Message: err.Error()}
	}

	data, marshalErr := json.MarshalIndent(errorEnvelope{Error: body}, "", "  ")
	if marshalErr != nil {
		fmt.Fprintf(w, `{"error":{"code":"RUNTIME_ERROR","message":"%s"}}`+"\n", marshalErr.Error())
		return code
	}
	fmt.Fprintf(w, "%s\n", data)
	return code
}
