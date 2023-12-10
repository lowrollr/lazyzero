

from typing import Tuple
import pgx
import jax.numpy as jnp
import jax
from core.envs.env import Env, EnvConfig, EnvState


class PgxEnv(Env):
    def __init__(self, env: pgx.core.Env, config: EnvConfig):
        super().__init__(
            env = env, 
            config = config
        )
        self._env: pgx.core.Env

    def get_action_shape(self) -> Tuple[int]:
        return (self._env.num_actions,)
    
    def get_observation_shape(self) -> Tuple[int]:
        return self._env.observation_shape
    
    def num_players(self) -> int:
        return self._env.num_players

    def step(self, state: EnvState, action: jnp.ndarray) -> Tuple[EnvState, jnp.ndarray]:
        # returns state, observation, reward, terminated
        env_state = self._env.step(state._state, action)
        return state.replace(
            legal_action_mask=env_state.legal_action_mask,
            reward=env_state.rewards,
            cur_player_id=env_state.current_player,
            _state=env_state,
            _observation=env_state.observation,
        ), env_state.terminated

    def reset(self, key: jax.random.PRNGKey) -> Tuple[EnvState, jnp.ndarray]:
        cls_key, base_key = jax.random.split(key)
        env_state = self._env.init(base_key)
        return EnvState(
            key=cls_key,
            legal_action_mask=env_state.legal_action_mask,
            cur_player_id=env_state.current_player,
            reward=env_state.rewards,
            _state=env_state,
            _observation=env_state.observation,
        ), env_state.terminated
        

def make_pgx_env(env_name, **kwargs) -> PgxEnv:
    env = pgx.make(env_name, **kwargs)
    return PgxEnv(env, config=EnvConfig(
        env_pkg='pgx',
        env_name=env_name,
        base_config=kwargs
    ))