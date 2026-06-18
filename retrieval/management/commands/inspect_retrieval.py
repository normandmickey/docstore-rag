import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from pgvector.django import CosineDistance

from control.models import Workspace
from documents.models import Chunk, Document
from providers import embed_texts, rewrite_question
from retrieval.service import retrieve_chunks


DEFAULT_VARIANTS = {
    "employee_pto_approval_001": [
        "PTO approval",
        "paid time off approval",
        "does paid time off require supervisor approval",
        "manager approval for time off",
        "time off requests approval",
    ],
    "employee_coworking_reimbursement_001": [
        "coworking reimbursement",
        "co-working reimbursement",
        "workspace reimbursement",
        "shared office reimbursement",
    ],
    "employee_home_office_furniture_001": [
        "home office furniture reimbursement",
        "desk and chair reimbursement",
        "home office expense policy",
        "office equipment reimbursement",
    ],
}

DEFAULT_PRESENCE_TERMS = {
    "employee_pto_approval_001": [
        "pto",
        "paid time off",
        "manager approval",
        "approval",
        "supervisor approval",
        "request time off",
    ],
    "employee_coworking_reimbursement_001": [
        "coworking",
        "co-working",
        "reimbursement",
        "workspace reimbursement",
        "shared workspace",
    ],
    "employee_home_office_furniture_001": [
        "home office",
        "furniture",
        "desk",
        "chair",
        "expense reimbursement",
        "office equipment",
    ],
}


class Command(BaseCommand):
    help = "Inspect corpus presence and retrieval candidates for eval questions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default="evals/employee_workspace_eval.jsonl",
            help="Path to JSONL eval file relative to repo root.",
        )
        parser.add_argument(
            "--ids",
            default="",
            help="Comma-separated eval ids to inspect. Defaults to the three known employee misses.",
        )
        parser.add_argument(
            "--workspace",
            default="",
            help="Optional workspace slug override for all evals.",
        )
        parser.add_argument(
            "--top-k",
            type=int,
            default=10,
            help="Top-k results to keep from the app retriever.",
        )
        parser.add_argument(
            "--candidate-count",
            type=int,
            default=10,
            help="How many rows per raw retrieval channel to capture.",
        )
        parser.add_argument(
            "--save",
            default="",
            help="Optional path to save the JSON report relative to repo root.",
        )

    def handle(self, *args, **options):
        repo_root = Path(__file__).resolve().parents[3]
        eval_path = repo_root / options["file"]
        if not eval_path.exists():
            raise CommandError(f"Eval file not found: {eval_path}")

        rows = []
        with eval_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))

        if not rows:
            raise CommandError(f"No eval rows found in {eval_path}")

        selected_ids = [
            part.strip() for part in (options["ids"] or "").split(",") if part.strip()
        ] or [
            "employee_pto_approval_001",
            "employee_coworking_reimbursement_001",
            "employee_home_office_furniture_001",
        ]

        row_map = {row.get("id"): row for row in rows}
        missing_ids = [row_id for row_id in selected_ids if row_id not in row_map]
        if missing_ids:
            raise CommandError(f"Eval ids not found in file: {', '.join(missing_ids)}")

        report_rows = []
        for row_id in selected_ids:
            row = row_map[row_id]
            workspace_slug = options["workspace"] or row.get("workspace_slug") or ""
            workspace = Workspace.objects.filter(slug=workspace_slug).select_related("tenant").first()
            if workspace is None:
                raise CommandError(f"Workspace not found for {row_id}: {workspace_slug}")

            self.stdout.write(self.style.NOTICE(f"Inspecting {row_id} ({workspace_slug})"))
            report_rows.append(
                inspect_eval_row(
                    row=row,
                    workspace=workspace,
                    top_k=options["top_k"],
                    candidate_count=options["candidate_count"],
                )
            )

        report = {
            "eval_file": str(eval_path.relative_to(repo_root)),
            "ids": selected_ids,
            "top_k": options["top_k"],
            "candidate_count": options["candidate_count"],
            "rows": report_rows,
        }

        if options["save"]:
            save_path = repo_root / options["save"]
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Saved report to {options['save']}"))

        self.stdout.write(json.dumps(report, indent=2))


def inspect_eval_row(*, row, workspace, top_k, candidate_count):
    tenant = workspace.tenant
    query = row["question"].strip()
    eval_id = row.get("id") or ""
    variants = [query] + DEFAULT_VARIANTS.get(eval_id, [])
    presence_terms = DEFAULT_PRESENCE_TERMS.get(eval_id, _fallback_presence_terms(query))

    base_qs = (
        Chunk.objects.filter(
            tenant=tenant,
            document__status=Document.STATUS_READY,
            document__workspace_assignments__workspace=workspace,
        )
        .select_related("document")
        .distinct()
    )

    presence = inspect_presence(base_qs, presence_terms, limit_per_term=8)
    retrieval_runs = []
    for variant in variants:
        retrieval_runs.append(
            inspect_query_variant(
                base_qs=base_qs,
                workspace=workspace,
                tenant=tenant,
                query=variant,
                top_k=top_k,
                candidate_count=candidate_count,
            )
        )

    verdict = summarize_verdict(presence=presence, retrieval_runs=retrieval_runs)

    return {
        "id": eval_id,
        "workspace_slug": workspace.slug,
        "question": query,
        "expected_mode": row.get("expected_mode"),
        "presence_terms": presence_terms,
        "presence": presence,
        "retrieval_runs": retrieval_runs,
        "verdict": verdict,
    }


def inspect_presence(base_qs, terms, limit_per_term=8):
    docs = {}
    total_hits = 0
    term_rows = []
    for term in terms:
        term_qs = base_qs.filter(
            text__icontains=term,
        ).order_by("document__filename", "chunk_index")[:limit_per_term]
        matches = []
        for chunk in term_qs:
            matches.append({
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "document": chunk.document.filename,
                "chunk_index": chunk.chunk_index,
                "text_excerpt": excerpt(chunk.text, term),
            })
            docs[str(chunk.document_id)] = chunk.document.filename
            total_hits += 1
        term_rows.append({
            "term": term,
            "match_count": len(matches),
            "matches": matches,
        })

    return {
        "term_results": term_rows,
        "total_hits": total_hits,
        "documents_with_hits": [{"document_id": doc_id, "document": name} for doc_id, name in docs.items()],
        "corpus_presence": total_hits > 0,
    }


def inspect_query_variant(*, base_qs, workspace, tenant, query, top_k, candidate_count):
    standalone_query = rewrite_question(query)
    query_vector = embed_texts([standalone_query])[0]

    vector_candidates = list(
        base_qs.annotate(distance=CosineDistance("embedding", query_vector)).order_by("distance")[:candidate_count]
    )
    metadata_candidates = list(
        base_qs.filter(metadata_embedding__isnull=False)
        .annotate(metadata_distance=CosineDistance("metadata_embedding", query_vector))
        .order_by("metadata_distance")[:candidate_count]
    )
    question_candidates = list(
        base_qs.filter(question_embedding__isnull=False)
        .annotate(question_distance=CosineDistance("question_embedding", query_vector))
        .order_by("question_distance")[:candidate_count]
    )

    search_query = SearchQuery(standalone_query, search_type="plain")
    lexical_candidates = list(
        base_qs.annotate(
            search_vector=SearchVector("text"),
            lexical_rank=SearchRank(SearchVector("text"), search_query),
        )
        .filter(search_vector=search_query)
        .order_by("-lexical_rank")[:candidate_count]
    )

    app_results = retrieve_chunks(
        tenant=tenant,
        workspace=workspace,
        query=query,
        top_k=top_k,
    )

    return {
        "query": query,
        "standalone_query": standalone_query,
        "app_results": [serialize_app_result(idx + 1, row) for idx, row in enumerate(app_results)],
        "raw_channels": {
            "vector": [serialize_vector_candidate(idx + 1, row, "distance") for idx, row in enumerate(vector_candidates)],
            "metadata": [serialize_vector_candidate(idx + 1, row, "metadata_distance") for idx, row in enumerate(metadata_candidates)],
            "question": [serialize_vector_candidate(idx + 1, row, "question_distance") for idx, row in enumerate(question_candidates)],
            "lexical": [serialize_lexical_candidate(idx + 1, row) for idx, row in enumerate(lexical_candidates)],
        },
    }


def serialize_app_result(rank, row):
    return {
        "rank": rank,
        "chunk_id": row.id,
        "document_id": row.document_id,
        "document": row.document.filename,
        "chunk_index": row.chunk_index,
        "distance": safe_float(getattr(row, "distance", None)),
        "relevance_score": safe_float(getattr(row, "relevance_score", None)),
        "metadata_relevance_score": safe_float(getattr(row, "metadata_relevance_score", None)),
        "question_relevance_score": safe_float(getattr(row, "question_relevance_score", None)),
        "lexical_score": safe_float(getattr(row, "lexical_score", None)),
        "blended_score": safe_float(getattr(row, "blended_score", None)),
        "metadata_text": getattr(row, "metadata_text", ""),
        "question_text": getattr(row, "question_text", ""),
        "text": getattr(row, "text", ""),
        "metadata_json": getattr(row, "metadata_json", {}) or {},
    }


def serialize_vector_candidate(rank, row, field_name):
    return {
        "rank": rank,
        "chunk_id": row.id,
        "document_id": row.document_id,
        "document": row.document.filename,
        "chunk_index": row.chunk_index,
        field_name: safe_float(getattr(row, field_name, None)),
        "metadata_text": getattr(row, "metadata_text", ""),
        "question_text": getattr(row, "question_text", ""),
        "text": getattr(row, "text", ""),
    }


def serialize_lexical_candidate(rank, row):
    return {
        "rank": rank,
        "chunk_id": row.id,
        "document_id": row.document_id,
        "document": row.document.filename,
        "chunk_index": row.chunk_index,
        "lexical_rank": safe_float(getattr(row, "lexical_rank", None)),
        "metadata_text": getattr(row, "metadata_text", ""),
        "question_text": getattr(row, "question_text", ""),
        "text": getattr(row, "text", ""),
    }


def summarize_verdict(*, presence, retrieval_runs):
    corpus_presence = bool(presence.get("corpus_presence"))
    top_exact = retrieval_runs[0]["app_results"] if retrieval_runs else []
    exact_docs = [row["document"] for row in top_exact[:3]]
    exact_best = top_exact[0] if top_exact else None

    if not corpus_presence:
        label = "not_present_in_corpus"
    elif exact_best and (exact_best.get("blended_score") or 0) >= 0.65:
        label = "present_and_retrieved_strongly"
    elif exact_best and (exact_best.get("blended_score") or 0) >= 0.45:
        label = "present_and_retrieved_weakly"
    else:
        variant_hit = False
        for run in retrieval_runs[1:]:
            app_results = run.get("app_results") or []
            if app_results and ((app_results[0].get("blended_score") or 0) >= 0.45):
                variant_hit = True
                break
        label = "present_but_not_retrieved_for_exact_query" if variant_hit or corpus_presence else "unclear"

    return {
        "label": label,
        "corpus_presence": corpus_presence,
        "top_exact_documents": exact_docs,
        "top_exact_best": exact_best,
    }


def _fallback_presence_terms(query):
    return [token for token in re.findall(r"[a-z0-9][a-z0-9\-]+", query.lower()) if len(token) >= 4][:6]


def excerpt(text, needle, width=220):
    haystack = text or ""
    lower = haystack.lower()
    target = (needle or "").lower()
    idx = lower.find(target)
    if idx < 0:
        return haystack[:width]
    start = max(0, idx - width // 3)
    end = min(len(haystack), idx + len(needle) + (2 * width // 3))
    snippet = haystack[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(haystack):
        snippet = snippet + "..."
    return snippet


def safe_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None
