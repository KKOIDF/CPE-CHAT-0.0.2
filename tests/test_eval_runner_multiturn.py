import unittest

from eval_runner import (
    build_eval_request_payloads,
    case_conversation_id,
    sort_cases_for_execution,
)


class TestEvalRunnerMultiturn(unittest.TestCase):
    def test_sort_cases_for_execution_orders_conversation_by_turn(self) -> None:
        cases = [
            {"id": "single_1", "question": "one"},
            {"id": "conv_b_2", "conversation_id": "conv-b", "turn_index": 2, "question": "b2"},
            {"id": "conv_a_2", "conversation_id": "conv-a", "turn_index": 2, "question": "a2"},
            {"id": "conv_a_1", "conversation_id": "conv-a", "turn_index": 1, "question": "a1"},
            {"id": "conv_b_1", "conversation_id": "conv-b", "turn_index": 1, "question": "b1"},
        ]

        ordered = sort_cases_for_execution(cases)
        ordered_ids = [str(case.get("id")) for case in ordered]
        self.assertEqual(
            ordered_ids,
            ["single_1", "conv_b_1", "conv_b_2", "conv_a_1", "conv_a_2"],
        )

    def test_build_eval_request_payloads_adds_session_and_messages(self) -> None:
        case = {
            "id": "mt_002",
            "question": "สรุปสั้นๆ",
            "expected_domain": "curriculum",
            "conversation_id": "conv-1",
            "turn_index": 2,
        }
        history = [
            {"role": "user", "content": "วิชาเลือกมีอะไรบ้าง"},
            {"role": "assistant", "content": "มีวิชาเลือก 12 หน่วยกิต"},
        ]

        retrieval_payload, answer_payload, conversation_id = build_eval_request_payloads(case, history)

        self.assertEqual(conversation_id, "conv-1")
        self.assertEqual(case_conversation_id(case), "conv-1")
        self.assertEqual(retrieval_payload["session_id"], "conv-1")
        self.assertEqual(answer_payload["session_id"], "conv-1")
        self.assertEqual(answer_payload["messages"][-1]["content"], "สรุปสั้นๆ")
        self.assertEqual(answer_payload["messages"][0]["content"], "วิชาเลือกมีอะไรบ้าง")

    def test_single_turn_payload_stays_minimal(self) -> None:
        case = {
            "id": "single_1",
            "question": "CPE 342 คือวิชาอะไร",
            "expected_domain": "curriculum",
        }

        retrieval_payload, answer_payload, conversation_id = build_eval_request_payloads(case, [])

        self.assertEqual(conversation_id, "")
        self.assertNotIn("session_id", retrieval_payload)
        self.assertNotIn("session_id", answer_payload)
        self.assertNotIn("messages", answer_payload)


if __name__ == "__main__":
    unittest.main()
