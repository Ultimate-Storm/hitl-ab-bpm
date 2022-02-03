from datetime import datetime

from models import db
from models.utils import CASCADING_DELETE


class BatchPolicy(db.Model):
    __tablename__ = 'batch_policy'
    id = db.Column(db.Integer, primary_key=True)
    batch_size = db.Column(db.Integer, nullable=False)
    process_id = db.Column(db.Integer, db.ForeignKey('process.id'))
    time_added = db.Column(db.DateTime, nullable=False, default=datetime.now())
    execution_strategies = db.relationship('ExecutionStrategyBaPol', backref='batch_policy', cascade=CASCADING_DELETE)
    process_instances = db.relationship('ProcessInstance', backref='batch_policy', cascade=CASCADING_DELETE)
    batch_policy_proposal = db.relationship('BatchPolicyProposal',
                                            backref='batch_policy',
                                            cascade=CASCADING_DELETE,
                                            uselist=False)


class ExecutionStrategyBaPol(db.Model):
    __tablename__ = "execution_strategy_bapol"
    batch_policy_id = db.Column(db.Integer, db.ForeignKey('batch_policy.id'), primary_key=True)
    customer_category = db.Column(db.String(100), primary_key=True)
    exploration_probability_a = db.Column(db.Float, default=0.5, nullable=False)
    exploration_probability_b = db.Column(db.Float, default=0.5, nullable=False)


def get_latest_bapol_entry(process_id: int):
    return BatchPolicy.query.order_by(BatchPolicy.time_added.desc()) \
        .filter(BatchPolicy.process_id == process_id).first()


def append_process_instance_to_bapol(process_id: int, process_instance):
    relevant_bapol = get_latest_bapol_entry(process_id)
    relevant_bapol.process_instances.append(process_instance)


def get_current_bapol_data(process_id: int) -> dict:
    """ Get the latest (= currently active) bapol of specified process """
    latest_bapol = get_latest_bapol_entry(process_id)
    exec_strats_rows: [ExecutionStrategyBaPol] = latest_bapol.execution_strategies
    exec_strats_dict = []
    for elem in exec_strats_rows:
        exec_strat = {
            "customerCategory": elem.customer_category,
            "explorationProbabilityA": elem.exploration_probability_a,
            "explorationProbabilityB": elem.exploration_probability_b
        }
        exec_strats_dict.append(exec_strat)
    data = {
        "baPolId": latest_bapol.id,
        "prevBaPolPropId": latest_bapol.batch_policy_proposal.id,
        "lastModified": latest_bapol.time_added,
        "batchSize": latest_bapol.batch_size,
        "processId": latest_bapol.process_id,
        "executionStrategy": exec_strats_dict
    }
    return data


def get_current_bapol_data_active_process():
    """ Get the latest (= currently active) bapol of specified process """
    from models.process import get_active_process_metadata
    return get_current_bapol_data(get_active_process_metadata().get('id'))


def is_latest_batch_done(process_id: int) -> bool:
    latest_bapol = BatchPolicy.query.order_by(BatchPolicy.time_added.desc()) \
        .filter(BatchPolicy.process_id == process_id).first()
    if latest_bapol.batch_size == latest_bapol.instances.count():
        return True
    elif latest_bapol.batch_size < latest_bapol.instances.count():
        return False
    else:
        raise RuntimeError("Batch Policy size has been exceeded. Illegal state.")


def is_latest_batch_active_process_done() -> bool:
    from models.process import get_active_process_metadata
    return is_latest_batch_done(get_active_process_metadata().get('id'))


def get_batch_size_sum(process_id: int) -> int:
    relevant_batch_policies = BatchPolicy.query.filter(BatchPolicy.process_id == process_id)
    batch_size_counter = 0
    for bapol in relevant_batch_policies:
        batch_size_counter += bapol.batch_size
    return batch_size_counter
