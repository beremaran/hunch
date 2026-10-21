"""Sensitive-category keywords and the embedding half of the detector (Phase 5)."""

from __future__ import annotations

import numpy as np
import pytest

from hunch.config import load_config
from hunch.privacy.categories import (
    CATEGORY_KEYWORDS,
    CATEGORY_PROTOTYPES,
    CategoryDetector,
    keyword_categories,
)
from tests.fakes import HashEmbedder

CATEGORIES = load_config().privacy.categories

POSITIVES = [
    # health
    ("health", "The doctor says I was diagnosed with type 2 diabetes last week."),
    ("health", "I'm having knee surgery on Thursday."),
    ("health", "My mom has cancer and we just found out."),
    ("health", "I broke my wrist skiing, so typing is slow."),
    ("health", "I'm pregnant! We haven't told anyone yet."),
    ("health", "my dad is in the hospital after a stroke"),
    ("health", "I've been sick for four days and my doctor wants more tests."),
    ("health", "I tested positive for covid this morning."),
    # mental_health
    ("mental_health", "My therapist thinks I should write things down."),
    ("mental_health", "I was diagnosed with depression two years ago."),
    ("mental_health", "I had a panic attack on the bus."),
    ("mental_health", "I'm taking sertraline and it makes me tired."),
    ("mental_health", "I'm in therapy and it's hard."),
    ("mental_health", "I've been so depressed since March."),
    ("mental_health", "I was diagnosed with burnout and I'm on leave."),
    ("mental_health", "my anxiety has been awful this month"),
    ("mental_health", "I used to self-harm when I was a teenager."),
    # money
    ("money", "My salary is 62k and I still can't save anything."),
    ("money", "I can't make rent this month."),
    ("money", "I owe my brother 3000 euros."),
    ("money", "We're drowning in credit card debt."),
    ("money", "I earn about 4000 a month before tax."),
    ("money", "honestly I'm broke until Friday"),
    ("money", "I'm behind on my mortgage payments."),
    ("money", "Money is really tight right now."),
    # relationship
    ("relationship", "My ex keeps texting me at night."),
    ("relationship", "We broke up on Sunday."),
    ("relationship", "I think my husband is cheating on me."),
    ("relationship", "My wife and I keep fighting about the kids."),
    ("relationship", "I had a huge fight with my mom yesterday."),
    ("relationship", "I haven't spoken to my dad in two years."),
    ("relationship", "We're getting divorced."),
    ("relationship", "My girlfriend yelled at me again last night."),
    # sexuality
    ("sexuality", "I think I'm gay but nobody knows."),
    ("sexuality", "I came out to my parents last weekend."),
    ("sexuality", "I'm bisexual and still figuring it out."),
    ("sexuality", "My sex life has been nonexistent lately."),
    ("sexuality", "I'm on hrt now and it's going well."),
    ("sexuality", "I'm attracted to both men and women."),
    ("sexuality", "my son just came out as gay"),
    # legal
    ("legal", "I got arrested last night."),
    ("legal", "I have to go to court on Monday."),
    ("legal", "My lawyer says the lawsuit could take years."),
    ("legal", "My visa expires in March and I'm scared."),
    ("legal", "The police showed up at my door yesterday."),
    ("legal", "My neighbour is suing me over the fence."),
    ("legal", "I'm worried about being deported."),
    ("legal", "My work visa renewal got delayed."),
    # work_conflict
    ("work_conflict", "I got fired today."),
    ("work_conflict", "My boss yelled at me in front of everyone."),
    ("work_conflict", "HR called me in about a complaint."),
    ("work_conflict", "They put me on a performance improvement plan."),
    ("work_conflict", "I hate my manager so much."),
    ("work_conflict", "I got a written warning for being late."),
    ("work_conflict", "I was pushed out of the team last month."),
    ("work_conflict", "My coworker keeps taking credit for my work."),
    # religion_politics
    ("religion_politics", "I'm losing my faith and I don't know who to tell."),
    ("religion_politics", "I voted for the Greens this time."),
    ("religion_politics", "I'm a practicing Muslim and it matters to me."),
    ("religion_politics", "I went to the climate march on Saturday."),
    ("religion_politics", "I go to church every Sunday."),
    ("religion_politics", "I'm a socialist and it makes dinner with my family awkward."),
    # more framings
    ("relationship", "I got dumped yesterday."),
    ("relationship", "My mom and I aren't speaking right now."),
    ("money", "My landlord is evicting me next month."),
    ("legal", "I got a DUI last year and it still follows me."),
    ("sexuality", "I came out last year and things are better now."),
    ("work_conflict", "I lost my job in March."),
    ("health", "My dad has been in and out of the hospital since spring."),
]

NEAR_MISSES = [
    "My bank's app is down again.",
    "We watched a documentary about depression last night.",
    "The court near my flat is being renovated.",
    "I'm sick of this weather.",
    "Politics on tv is exhausting.",
    "Got paid today, pizza!",
    "I owe you one for the lift.",
    "I owe you a lot, thanks!",
    "My Visa card got declined at the shop.",
    "My visa for Japan arrived, can't wait for the trip.",
    "I broke my phone screen again.",
    "My exam is on Friday.",
    "My ex-boss sent me a nice email.",
    "I'm fired up about the new project!",
    "My boss asked me to bring coffee.",
    "My boss is on holiday this week.",
    "I need to see a dentist about my cavity.",
    "I'm burned out after the week, need a nap.",
    "I need therapy after that movie, lol.",
    "I pray it doesn't rain tomorrow.",
    "My girlfriend's birthday is tomorrow.",
    "My wife and I went to Rome last summer.",
    "I make 3 pizzas every Friday.",
    "I'm a bit anxious about the exam tomorrow.",
    "The church on the corner has a nice garden.",
    "I'm liberal with the salt.",
    "My trial subscription ends tomorrow.",
    "My probation period at the new job is six months.",
    "I cut myself shaving this morning.",
    "I went to the market and bought some apples.",
    "Can you recommend a good podcast?",
    "That reminds me, my keys are in the other room.",
    "She sued the company in a documentary I watched.",
    "The new tennis court opens on Monday.",
    "I'm going to court to play tennis with Sam.",
    "Sorry for the late reply, my phone died.",
    "The distance between us is only five minutes.",
    "I'm straight up exhausted today.",
]


def test_every_configured_category_has_keywords_and_prototypes() -> None:
    for cat in CATEGORIES:
        assert CATEGORY_KEYWORDS[cat], cat
        assert 5 <= len(CATEGORY_PROTOTYPES[cat]) <= 6, cat


@pytest.mark.parametrize(("category", "text"), POSITIVES)
def test_keyword_positive(category: str, text: str) -> None:
    assert keyword_categories(text, CATEGORIES) == [category]


@pytest.mark.parametrize("text", NEAR_MISSES)
def test_keyword_near_miss(text: str) -> None:
    assert keyword_categories(text, CATEGORIES) == []


def test_keyword_order_follows_the_categories_argument() -> None:
    text = "My therapist says my boss yelled at me too much, and I can't make rent."
    assert keyword_categories(text, CATEGORIES) == ["mental_health", "money", "work_conflict"]
    assert keyword_categories(text, ["work_conflict", "money"]) == ["work_conflict", "money"]


def test_keyword_handles_curly_apostrophes_and_case() -> None:
    assert keyword_categories("I CAN’T MAKE RENT", CATEGORIES) == ["money"]


def test_unknown_category_is_an_error() -> None:
    with pytest.raises(ValueError, match="astrology"):
        keyword_categories("hello", ["health", "astrology"])
    with pytest.raises(ValueError, match="astrology"):
        CategoryDetector(["health", "astrology"], HashEmbedder(), 0.5)


def test_detector_without_embedder_is_keywords_only() -> None:
    detector = CategoryDetector(CATEGORIES, None, 0.5)
    assert detector.similarities(np.ones(16, dtype=np.float32)) == {}
    assert detector.detect("I got fired today.", None) == ["work_conflict"]
    assert detector.detect("Nice weather today.", np.ones(16, dtype=np.float32)) == []


class _CountingEmbedder(HashEmbedder):
    def __init__(self) -> None:
        super().__init__(dim=64)
        self.document_calls: list[int] = []

    def embed_documents(self, texts):  # type: ignore[no-untyped-def]
        self.document_calls.append(len(texts))
        return super().embed_documents(texts)

    def embed_queries(self, texts):  # type: ignore[no-untyped-def]
        return HashEmbedder.embed_documents(self, texts)  # queries are not counted


def test_prototypes_are_embedded_once_in_one_call() -> None:
    embedder = _CountingEmbedder()
    detector = CategoryDetector(CATEGORIES, embedder, 0.5)
    expected = sum(len(CATEGORY_PROTOTYPES[c]) for c in CATEGORIES)
    assert embedder.document_calls == [expected]
    detector.detect("anything", embedder.embed_queries(["anything"])[0])
    detector.similarities(embedder.embed_queries(["something else"])[0])
    assert embedder.document_calls == [expected]


def test_similarity_is_max_dot_product_per_category() -> None:
    embedder = HashEmbedder(dim=64)
    detector = CategoryDetector(CATEGORIES, embedder, 0.5)
    prototype = CATEGORY_PROTOTYPES["money"][0]
    query = embedder.embed_queries([prototype])[0]
    sims = detector.similarities(query)
    assert set(sims) == set(CATEGORIES)
    assert sims["money"] == pytest.approx(1.0, abs=1e-5)
    assert all(sims[c] < 1.0 - 1e-3 for c in CATEGORIES if c != "money")
    # a (1, dim) query works like a flat one
    assert detector.similarities(query[None, :]) == sims


def test_embedding_catches_a_paraphrase_without_keywords() -> None:
    embedder = HashEmbedder(dim=64)
    detector = CategoryDetector(CATEGORIES, embedder, 0.6)
    # a close copy of a prototype with a few words changed: no keyword, but similar
    text = "I earn barely enough to cover my bills, let alone save anything at all."
    assert keyword_categories(text, CATEGORIES) == []
    vec = embedder.embed_queries([text])[0]
    assert detector.detect(text, vec) == ["money"]


def test_threshold_decides_the_embedding_half() -> None:
    embedder = HashEmbedder(dim=64)
    text = "I earn barely enough to cover my bills, let alone save anything at all."
    vec = embedder.embed_queries([text])[0]
    low = CategoryDetector(CATEGORIES, embedder, 0.6)
    high = CategoryDetector(CATEGORIES, embedder, 0.999)
    assert low.detect(text, vec) == ["money"]
    assert high.detect(text, vec) == []


def test_unrelated_text_stays_below_a_sensible_threshold() -> None:
    embedder = HashEmbedder(dim=256)
    detector = CategoryDetector(CATEGORIES, embedder, 0.55)
    text = "Pasta tonight, maybe with mushrooms."
    assert detector.detect(text, embedder.embed_queries([text])[0]) == []


def test_keyword_hit_does_not_need_similarity() -> None:
    embedder = HashEmbedder(dim=64)
    detector = CategoryDetector(CATEGORIES, embedder, 0.999)
    text = "I can't make rent this month."
    assert detector.detect(text, embedder.embed_queries([text])[0]) == ["money"]


def test_detect_returns_config_order() -> None:
    embedder = HashEmbedder(dim=64)
    detector = CategoryDetector(CATEGORIES, embedder, 0.999)
    text = "I got fired, my boss yelled, and now I can't make rent."
    assert detector.detect(text, None) == ["money", "work_conflict"]
