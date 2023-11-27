
from typing import Tuple
from flax import struct
from dataclasses import dataclass
import jax
import jax.numpy as jnp

from core_jax.envs.env import Env, EnvState


@dataclass
class EvaluatorConfig:
    epsilon: float


@struct.dataclass
class EvaluatorState:
    key: jax.random.PRNGKey

class Evaluator:
    def __init__(self,
        config: EvaluatorConfig,
        *args,
        **kwargs
    ):
        self.config = config
        self.args = args
        self.kwargs = kwargs

    def reset(self, key: jax.random.PRNGKey) -> EvaluatorState:
        return EvaluatorState(key=key)
    
    def evaluate(self, 
        evaluator_state: EvaluatorState, 
        env: Env, 
        env_state: EnvState, 
        *args
    ) -> Tuple[EvaluatorState]:
        raise NotImplementedError() 
    
    def choose_action(self, 
        evaluator_state: EvaluatorState, 
        env: Env,
        env_state: EnvState,
    ) -> Tuple[EvaluatorState, jnp.ndarray]:
        raise NotImplementedError()
    
    def step_evaluator(self, 
        evaluator_state: EvaluatorState, 
        actions: jnp.ndarray, 
        terminated: jnp.ndarray
    ) -> EvaluatorState:
        return evaluator_state
    
    def get_raw_policy(self, evaluator_state: EvaluatorState) -> jnp.ndarray:
        raise NotImplementedError()