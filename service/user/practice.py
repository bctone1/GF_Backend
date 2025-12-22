# # service/user/practice.py
# from __future__ import annotations
#
# """
# DEPRECATED (shim)
# - 기존 import 경로 호환을 위해 잠시 유지
# - 실제 구현은 service/user/practice/* 로 이동됨
# """
#
# from service.user.practice.ownership import (
#     ensure_my_session,
#     ensure_my_session_model,
#     ensure_my_response,
# )
#
# from service.user.practice.orchestrator import (
#     run_practice_turn_for_session,
#     ensure_session_settings,
# )
#
# from service.user.practice.models_sync import (
#     init_models_for_session_from_class,
#     resolve_runtime_model,
#     is_enabled_runtime_model,
# )
#
# from service.user.practice.turn_runner import (
#     run_practice_turn,
# )
#
# from service.user.practice.retrieval import (
#     make_retrieve_fn_for_practice,
# )
#
# from service.user.practice.ids import (
#     coerce_int_list,
#     get_session_knowledge_ids,
#     has_any_response,
# )
#
# # params.py에 실제로 존재하는 것만 export해야 함
# from service.user.practice.params import (
#     normalize_generation_params_dict,
#     get_default_generation_params,
#     get_model_max_output_tokens,
#     clamp_generation_params_max_tokens,
# )
#
# __all__ = [
#     "ensure_my_session",
#     "ensure_my_session_model",
#     "ensure_my_response",
#     "run_practice_turn_for_session",
#     "ensure_session_settings",
#     "init_models_for_session_from_class",
#     "resolve_runtime_model",
#     "is_enabled_runtime_model",
#     "run_practice_turn",
#     "make_retrieve_fn_for_practice",
#     "coerce_int_list",
#     "get_session_knowledge_ids",
#     "has_any_response",
#     "normalize_generation_params_dict",
#     "get_default_generation_params",
#     "get_model_max_output_tokens",
#     "clamp_generation_params_max_tokens",
# ]
