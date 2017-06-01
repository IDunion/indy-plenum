import pytest

from stp_core.loop.eventually import eventually
from plenum.test.pool_transactions.conftest import clientAndWallet1, \
    client1, wallet1, client1Connected, looper
from plenum.test.helper import checkViewNoForNodes, \
    sendReqsToNodesAndVerifySuffReplies

from plenum.test.test_node import get_master_primary_node


@pytest.mark.skip(reason='SOV-1020')
def test_view_not_changed_when_short_disconnection(txnPoolNodeSet, looper,
                                                   wallet1, client1,
                                                   client1Connected, tconf):
    """
    When primary is disconnected but not long enough to trigger the timeout,
    view change should not happen
    """
    pr_node = get_master_primary_node(txnPoolNodeSet)
    view_no = checkViewNoForNodes(txnPoolNodeSet)

    lost_pr_calls = {node.name: node.spylog.count(
        node.lost_master_primary.__name__) for node in txnPoolNodeSet
                           if node != pr_node}

    prp_inst_chg_calls = {node.name: node.spylog.count(
        node.propose_view_change.__name__) for node in txnPoolNodeSet
                           if node != pr_node}

    recv_inst_chg_calls = {node.name: node.spylog.count(
        node.processInstanceChange.__name__) for node in txnPoolNodeSet
                           if node != pr_node}

    def chk1():
        # Check that non-primary nodes detects losing connection with
        # primary
        for node in txnPoolNodeSet:
            if node != pr_node:
                assert node.spylog.count(node.lost_master_primary.__name__) \
                       > lost_pr_calls[node.name]

    def chk2():
        # Schedule an instance change but do not send it
        # since primary joins again
        for node in txnPoolNodeSet:
            if node != pr_node:
                assert node.spylog.count(node.propose_view_change.__name__) \
                       > prp_inst_chg_calls[node.name]
                assert node.spylog.count(node.processInstanceChange.__name__) \
                       == recv_inst_chg_calls[node.name]

    # Disconnect master's primary
    for node in txnPoolNodeSet:
        if node != pr_node:
            node.nodestack.getRemote(pr_node.nodestack.name).disconnect()

    timeout = min(tconf.ToleratePrimaryDisconnection-1, 1)
    looper.run(eventually(chk1, retryWait=.2, timeout=timeout))

    # Reconnect master's primary
    for node in txnPoolNodeSet:
        if node != pr_node:
            node.nodestack.retryDisconnected()

    looper.run(eventually(chk2, retryWait=.2, timeout=timeout+1))

    def chk3():
        # Check the view does not change
        with pytest.raises(AssertionError):
            assert checkViewNoForNodes(txnPoolNodeSet) == view_no + 1

    looper.run(eventually(chk3, retryWait=1, timeout=10))

    # Send some requests and make sure the request execute
    sendReqsToNodesAndVerifySuffReplies(looper, wallet1, client1, 5)
