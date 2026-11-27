<?php
/**
 * CRM-IDINT-001R test harness: runs the real custom PHP (IdentityPolicy, IdentityAuditor,
 * IdentityGuard, the hooks and the record hooks) in the order the platform runs it, on the
 * fake persistence layer of identity_fake.php, with the platform's real hook interfaces,
 * options and GeneralInvoker loaded from the pinned reference.
 *
 * It prints one line per scenario:   <name>=<outcome>|<audit records written>
 * where outcome is ok, Forbidden or BadRequest and an audit record reads
 * relationship:recordType:recordId:previous>new. Some scenarios print extra state lines.
 *
 * Usage: php identity_harness.php <reference dir> <path to custom/Espo/Custom>
 */

namespace {
    use CrmTest\FakeEntity;
    use CrmTest\FakePlatform;
    use Espo\Core\Exceptions\BadRequest;
    use Espo\Core\Exceptions\Forbidden;
    use Espo\Custom\Classes\Identity\IdentityPolicy as P;

    [, $reference, $root] = $argv;

    require $reference . '/vendor/autoload.php';
    require __DIR__ . '/identity_stubs.php';
    spl_autoload_register(function (string $class) use ($root): void {
        $prefix = 'Espo\\Custom\\';

        if (str_starts_with($class, $prefix)) {
            $file = $root . '/' . str_replace('\\', '/', substr($class, strlen($prefix))) . '.php';

            if (is_file($file)) {
                require $file;
            }
        }
    });
    require __DIR__ . '/identity_fake.php';

    function run(string $name, callable $fn, bool $admin = false): void
    {
        global $root;
        $p = new FakePlatform($root, $admin);

        try {
            $fn($p);
            $r = 'ok';
        } catch (Forbidden) {
            $r = 'Forbidden';
        } catch (BadRequest) {
            $r = 'BadRequest';
        }

        echo $name . '=' . $r . '|' . implode(',', $p->audits()) . "\n";
    }

    function line(string $name, mixed $value): void
    {
        echo $name . '=' . (is_string($value) ? $value : json_encode($value)) . "\n";
    }

    function newOf(string $type, array $f = []): FakeEntity
    {
        $e = new FakeEntity($type, true);
        $e->set($f);

        return $e;
    }

    function edit(FakeEntity $e, array $changes): FakeEntity
    {
        $e->set($changes);

        return $e;
    }

    /** POST /<Entity>: the platform discards a client-supplied identifier, then the record hooks, then the save. */
    function apiCreate(FakePlatform $p, string $type, array $data, array $options = []): FakeEntity
    {
        unset($data['id']);
        $e = newOf($type, $data);
        $p->recordCreateInput($e);
        $p->save($e, $options + ['api' => true]);

        return $e;
    }

    function firmLinks(FakePlatform $p, string $contact): string
    {
        return implode(',', $p->linkedFirms($contact));
    }

    function field(FakePlatform $p, string $type, string $id, string $attribute): string
    {
        return (string) ($p->rows[$type][$id][$attribute] ?? '');
    }

    // ---- pure policy ----
    echo 'policy.primary_broken=' . json_encode([P::primaryFirmBroken('a', ['b']), P::primaryFirmBroken('a', ['a', 'b']), P::primaryFirmBroken(null, []), P::primaryFirmBroken('', ['b'])]) . "\n";
    echo 'policy.unlink_primary=' . json_encode([P::unlinkRemovesPrimary('a', 'a'), P::unlinkRemovesPrimary('a', 'b'), P::unlinkRemovesPrimary(null, 'b')]) . "\n";
    $next = ['a' => 'b', 'b' => 'c', 'c' => null, 'x' => 'y', 'y' => 'x'];
    $nx = fn($id) => $next[$id] ?? null;
    echo 'policy.chain=' . json_encode([P::successorLoop('c', 'a', $nx), P::successorLoop('z', 'a', $nx), P::successorLoop('z', 'x', $nx), P::successorLoop('z', null, $nx)]) . "\n";
    echo 'policy.resolve=' . json_encode([P::resolve('a', $nx), P::resolve('c', $nx), P::resolve('x', $nx)]) . "\n";
    echo 'policy.status=' . json_encode([
        P::statusProblem('active', null, false), P::statusProblem('', null, false), P::statusProblem('retired', null, false),
        P::statusProblem('retired', 'b', true), P::statusProblem('superseded', null, false),
        P::statusProblem('superseded', 'b', false), P::statusProblem('superseded', 'b', true), P::statusProblem('gone', null, false),
    ]) . "\n";

    // ---- create (the platform has assigned the identifier before the before-save hook runs) ----
    run('create.plain_account', fn($p) => apiCreate($p, 'Account', ['name' => 'n']));
    run('create.plain_contact', fn($p) => apiCreate($p, 'Contact', ['lastName' => 'n']));
    run('create.plain_enquiry', fn($p) => apiCreate($p, 'Opportunity', ['name' => 'n']));
    run('create.plain_account_admin', fn($p) => apiCreate($p, 'Account', ['name' => 'n']), true);
    run('create.plain_contact_admin', fn($p) => apiCreate($p, 'Contact', ['lastName' => 'n']), true);
    foreach (['Account', 'Contact', 'Opportunity'] as $type) {
        run("create.supplied_id_is_never_used_$type", function ($p) use ($type) {
            $e = apiCreate($p, $type, ['id' => 'chosen']);
            line("supplied_id_used_$type", isset($p->rows[$type]['chosen']) ? 'yes' : 'no');
            line("supplied_id_created_$type", $p->count($type) === 1 && $e->getId() !== 'chosen' ? 'one-with-its-own-id' : 'other');
        });
    }
    run('create.import_option', fn($p) => $p->save(newOf('Account'), ['import' => true]));
    run('create.import_option_contact_admin', fn($p) => $p->save(newOf('Contact'), ['import' => true]), true);
    run('create.import_option_enquiry', fn($p) => $p->save(newOf('Opportunity'), ['import' => true]));
    run('create.import_with_identifier', fn($p) => $p->save(newOf('Account', ['id' => 'chosen']), ['import' => true]));
    run('create.with_parent', function ($p) { $p->seed('Account', 'p1'); apiCreate($p, 'Account', ['parentId' => 'p1']); });
    run('create.with_parent_audit_unwritable', function ($p) {
        $p->seed('Account', 'p1');
        $p->failAudit = true;
        try {
            apiCreate($p, 'Account', ['parentId' => 'p1']);
        } finally {
            line('accounts_left_after_failed_create', $p->count('Account'));
        }
    });
    run('create.contact_with_primary', function ($p) { $p->seed('Account', 'a1'); apiCreate($p, 'Contact', ['accountId' => 'a1']); line('links_after_create', firmLinks($p, 'c1')); });
    run('create.enquiry_with_firm', function ($p) { $p->seed('Account', 'a1'); apiCreate($p, 'Opportunity', ['accountId' => 'a1']); });
    run('create.contact_primary_not_linked', fn($p) => apiCreate($p, 'Contact', ['accountId' => 'a1', 'accountsIds' => ['a2']]));
    run('create.contact_primary_linked', fn($p) => apiCreate($p, 'Contact', ['accountId' => 'a1', 'accountsIds' => ['a1', 'a2']]));
    run('create.contact_links_without_primary', fn($p) => apiCreate($p, 'Contact', ['accountsIds' => ['a1', 'a2']]));
    run('create.contact_links_duplicate_ids', fn($p) => apiCreate($p, 'Contact', ['accountsIds' => ['a1', 'a1']]));
    run('create.contact_links_audit_unwritable', function ($p) {
        $p->failAudit = true;
        try {
            apiCreate($p, 'Contact', ['accountsIds' => ['a1', 'a2']]);
        } finally {
            line('create_links_contacts_left', $p->count('Contact'));
            line('create_links_link_rows_left', $p->linkRows());
        }
    });
    run('create.contact_links_audit_fails_on_second_link', function ($p) {
        // The first link is audited, the store then fails: the create is undone, links and all.
        $p->failAuditAfter = 2;
        try {
            apiCreate($p, 'Contact', ['accountsIds' => ['a1', 'a2']]);
        } finally {
            line('create_links2_contacts_left', $p->count('Contact'));
            line('create_links2_link_rows_left', $p->linkRows());
        }
    });
    run('create.contact_links_undo_cannot_delete', function ($p) {
        // R2: with the database refusing every write after the failure, the create still leaves nothing.
        $p->failAudit = true;
        $p->failExecutor = true;
        try {
            apiCreate($p, 'Contact', ['accountsIds' => ['a1']]);
        } finally {
            line('create_undo_fail_contacts_left', $p->count('Contact'));
            line('create_undo_fail_link_rows_left', $p->linkRows());
        }
    });
    run('create.retired_new', fn($p) => apiCreate($p, 'Account', ['identityStatus' => 'retired']));
    run('create.successor_new', function ($p) { $p->seed('Account', 'a1'); apiCreate($p, 'Account', ['identityStatus' => 'superseded', 'successorId' => 'a1']); });
    run('create.branches_input_refused', fn($p) => apiCreate($p, 'Account', ['branchesIds' => ['x']]));
    run('create.predecessors_input_refused', fn($p) => apiCreate($p, 'Contact', ['predecessorsIds' => ['x']]));

    // ---- edit ----
    run('edit.parent_change', function ($p) { $a = $p->seed('Account', 'a1', ['parentId' => 'p1']); edit($a, ['parentId' => 'p2']); $p->save($a); });
    run('edit.parent_clear', function ($p) { $a = $p->seed('Account', 'a1', ['parentId' => 'p1']); edit($a, ['parentId' => null]); $p->save($a); });
    run('edit.parent_same_value', function ($p) { $a = $p->seed('Account', 'a1', ['parentId' => 'p1']); edit($a, ['parentId' => 'p1']); $p->save($a); });
    run('edit.parent_audit_unwritable', function ($p) {
        $a = $p->seed('Account', 'a1', ['parentId' => 'p1']);
        $p->failAudit = true;
        edit($a, ['parentId' => 'p2']);
        try { $p->save($a); } finally { line('parent_after_refused_edit', field($p, 'Account', 'a1', 'parentId')); }
    });
    run('edit.parent_audit_readback_differs', function ($p) { $a = $p->seed('Account', 'a1', ['parentId' => 'p1']); $p->lieOnReadBack = true; edit($a, ['parentId' => 'p2']); $p->save($a); });
    run('edit.parent_admin', function ($p) { $a = $p->seed('Account', 'a1', ['parentId' => 'p1']); edit($a, ['parentId' => 'p2']); $p->save($a); }, true);
    run('edit.unrelated_field', function ($p) { $a = $p->seed('Account', 'a1'); edit($a, ['name' => 'x']); $p->save($a); });
    run('edit.contact_primary', function ($p) {
        $c = $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1']]);
        edit($c, ['accountId' => 'a2']);
        $p->save($c);
        line('links_after_primary_move', firmLinks($p, 'c1'));
    });
    run('edit.contact_primary_clear', function ($p) {
        $c = $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1']]);
        edit($c, ['accountId' => null]);
        $p->save($c);
        line('links_after_primary_clear', firmLinks($p, 'c1') ?: 'none');
    });
    run('edit.contact_drops_primary_link', function ($p) { $c = $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1', 'a2']]); edit($c, ['accountsIds' => ['a2']]); $p->save($c); });
    run('edit.contact_moves_primary_and_link', function ($p) {
        $c = $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1', 'a2']]);
        edit($c, ['accountId' => 'a2', 'accountsIds' => ['a2']]);
        $p->save($c);
        line('links_after_move', firmLinks($p, 'c1'));
    });
    run('edit.contact_clears_primary_and_drops_its_link', function ($p) {
        $c = $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1', 'a2']]);
        edit($c, ['accountId' => null, 'accountsIds' => ['a2']]);
        $p->save($c);
        line('links_after_clear', firmLinks($p, 'c1'));
    });
    run('edit.contact_clears_primary_and_all_links', function ($p) {
        $c = $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1']]);
        edit($c, ['accountId' => null, 'accountsIds' => []]);
        $p->save($c);
        line('links_after_clear_all', firmLinks($p, 'c1') ?: 'none');
        line('primary_after_clear_all', field($p, 'Contact', 'c1', 'accountId') ?: 'none');
    });
    run('edit.contact_adds_link', function ($p) { $c = $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1']]); edit($c, ['accountsIds' => ['a1', 'a3']]); $p->save($c); });
    run('edit.contact_adds_link_audit_unwritable', function ($p) {
        $c = $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1']]);
        $p->failAudit = true;
        edit($c, ['accountsIds' => ['a1', 'a3']]);
        try { $p->save($c); } finally { line('links_after_refused_add', firmLinks($p, 'c1')); }
    });
    run('edit.enquiry_firm', function ($p) { $o = $p->seed('Opportunity', 'o1', ['accountId' => 'a1']); edit($o, ['accountId' => 'a2']); $p->save($o); });
    run('edit.enquiry_firm_audit_unwritable', function ($p) { $o = $p->seed('Opportunity', 'o1', ['accountId' => 'a1']); $p->failAudit = true; edit($o, ['accountId' => 'a2']); $p->save($o); });
    run('edit.exception_primary_unlinked_then_other_edit', function ($p) {
        // An existing exception (primary not among the links) can still be edited for other reasons.
        $c = $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a2']]);
        edit($c, ['title' => 'x']);
        $p->save($c);
    });
    run('edit.branches_input_refused', function ($p) { $a = $p->seed('Account', 'a1'); edit($a, ['branchesIds' => ['x']]); $p->recordUpdateInput($a); });
    run('edit.predecessors_input_refused', function ($p) { $a = $p->seed('Contact', 'c1'); edit($a, ['predecessorsIds' => ['x']]); $p->recordUpdateInput($a); });
    run('edit.plain_input_allowed', function ($p) { $a = $p->seed('Account', 'a1'); edit($a, ['name' => 'x']); $p->recordUpdateInput($a); });

    // ---- over-length input ----
    run('length.title_at_limit', fn($p) => apiCreate($p, 'Contact', ['title' => str_repeat('a', 255)]));
    run('length.title_over_limit', fn($p) => apiCreate($p, 'Contact', ['title' => str_repeat('a', 256)]));
    run('length.title_over_limit_multibyte', fn($p) => apiCreate($p, 'Contact', ['title' => str_repeat("\u{e9}", 256)]));
    run('length.title_multibyte_at_limit', fn($p) => apiCreate($p, 'Contact', ['title' => str_repeat("\u{e9}", 255)]));
    run('length.account_name_over_limit', fn($p) => apiCreate($p, 'Account', ['name' => str_repeat('a', 250)]));
    run('length.title_over_limit_on_edit', function ($p) { $c = $p->seed('Contact', 'c1'); edit($c, ['title' => str_repeat('a', 300)]); $p->save($c); });
    run('length.legacy_long_value_untouched_on_other_edit', function ($p) { $c = $p->seed('Contact', 'c1', ['title' => str_repeat('a', 300)]); edit($c, ['description' => 'x']); $p->save($c); });
    run('length.nothing_stored_when_refused', function ($p) {
        try { apiCreate($p, 'Contact', ['title' => str_repeat('a', 256)]); } finally { line('contacts_stored_after_refused_title', $p->count('Contact')); }
    });

    // ---- retire and supersede ----
    run('status.retire', function ($p) { $a = $p->seed('Account', 'a1'); edit($a, ['identityStatus' => 'retired']); $p->save($a); });
    run('status.retire_contact', function ($p) { $a = $p->seed('Contact', 'c1'); edit($a, ['identityStatus' => 'retired']); $p->save($a); });
    run('status.supersede', function ($p) { $a = $p->seed('Account', 'a1'); $p->seed('Account', 'a2'); edit($a, ['identityStatus' => 'superseded', 'successorId' => 'a2']); $p->save($a); });
    run('status.supersede_contact', function ($p) { $a = $p->seed('Contact', 'c1'); $p->seed('Contact', 'c2'); edit($a, ['identityStatus' => 'superseded', 'successorId' => 'c2']); $p->save($a); });
    run('status.supersede_self', function ($p) { $a = $p->seed('Account', 'a1'); edit($a, ['identityStatus' => 'superseded', 'successorId' => 'a1']); $p->save($a); });
    run('status.supersede_missing', function ($p) { $a = $p->seed('Account', 'a1'); edit($a, ['identityStatus' => 'superseded', 'successorId' => 'nope']); $p->save($a); });
    run('status.supersede_wrong_kind', function ($p) { $a = $p->seed('Account', 'a1'); $p->seed('Contact', 'c9'); edit($a, ['identityStatus' => 'superseded', 'successorId' => 'c9']); $p->save($a); });
    run('status.supersede_cycle', function ($p) { $p->seed('Account', 'a2', ['identityStatus' => 'superseded', 'successorId' => 'a1']); $a = $p->seed('Account', 'a1'); edit($a, ['identityStatus' => 'superseded', 'successorId' => 'a2']); $p->save($a); });
    run('status.supersede_long_cycle', function ($p) { $p->seed('Account', 'a3', ['identityStatus' => 'superseded', 'successorId' => 'a1']); $p->seed('Account', 'a2', ['identityStatus' => 'superseded', 'successorId' => 'a3']); $a = $p->seed('Account', 'a1'); edit($a, ['identityStatus' => 'superseded', 'successorId' => 'a2']); $p->save($a); });
    run('status.supersede_into_a_chain', function ($p) { $p->seed('Account', 'a3'); $p->seed('Account', 'a2', ['identityStatus' => 'superseded', 'successorId' => 'a3']); $a = $p->seed('Account', 'a1'); edit($a, ['identityStatus' => 'superseded', 'successorId' => 'a2']); $p->save($a); });
    run('status.superseded_without_successor', function ($p) { $a = $p->seed('Account', 'a1'); edit($a, ['identityStatus' => 'superseded']); $p->save($a); });
    run('status.retired_with_successor', function ($p) { $a = $p->seed('Account', 'a1'); $p->seed('Account', 'a2'); edit($a, ['identityStatus' => 'retired', 'successorId' => 'a2']); $p->save($a); });
    run('status.active_with_successor', function ($p) { $a = $p->seed('Account', 'a1'); $p->seed('Account', 'a2'); edit($a, ['successorId' => 'a2']); $p->save($a); });
    run('status.unknown_value', function ($p) { $a = $p->seed('Account', 'a1'); edit($a, ['identityStatus' => 'deleted']); $p->save($a); });
    run('status.reactivate', function ($p) { $a = $p->seed('Account', 'a1', ['identityStatus' => 'retired']); edit($a, ['identityStatus' => 'active']); $p->save($a); });
    run('status.audit_unwritable', function ($p) { $a = $p->seed('Account', 'a1'); $p->failAudit = true; edit($a, ['identityStatus' => 'retired']); $p->save($a); });
    run('status.retire_admin', function ($p) { $a = $p->seed('Account', 'a1'); edit($a, ['identityStatus' => 'retired']); $p->save($a); }, true);

    // ---- links through the record link and unlink routes, and through the ORM directly ----
    run('link.contact_unlink_primary', function ($p) { $p->seed('Account', 'a1'); $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1']]); $p->recordUnlink('Contact', 'c1', 'accounts', 'a1'); });
    run('link.contact_unlink_primary_admin', function ($p) { $p->seed('Account', 'a1'); $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1']]); $p->recordUnlink('Contact', 'c1', 'accounts', 'a1'); }, true);
    run('link.contact_unlink_other', function ($p) {
        $p->seed('Account', 'a1'); $p->seed('Account', 'a2'); $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1', 'a2']]);
        $p->recordUnlink('Contact', 'c1', 'accounts', 'a2');
        line('links_left', firmLinks($p, 'c1'));
    });
    run('link.contact_link', function ($p) {
        $p->seed('Account', 'a1'); $p->seed('Account', 'a2'); $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1']]);
        $p->recordLink('Contact', 'c1', 'accounts', 'a2');
        line('links_now', firmLinks($p, 'c1'));
    });
    run('link.contact_link_audit_unwritable', function ($p) {
        $p->seed('Account', 'a2'); $p->seed('Contact', 'c1'); $p->failAudit = true;
        try { $p->recordLink('Contact', 'c1', 'accounts', 'a2'); } finally { line('links_after_refused_link', firmLinks($p, 'c1') ?: 'none'); }
    });
    run('link.contact_unlink_audit_unwritable', function ($p) {
        $p->seed('Account', 'a1'); $p->seed('Account', 'a2'); $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1', 'a2']]); $p->failAudit = true;
        try { $p->recordUnlink('Contact', 'c1', 'accounts', 'a2'); } finally { line('links_after_refused_unlink', firmLinks($p, 'c1')); }
    });
    run('link.firm_side_unlink_primary', function ($p) { $p->seed('Account', 'a1'); $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1']]); $p->recordUnlink('Account', 'a1', 'contacts', 'c1'); });
    run('link.firm_side_unlink_other', function ($p) {
        $p->seed('Account', 'a2'); $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1', 'a2']]);
        $p->recordUnlink('Account', 'a2', 'contacts', 'c1');
        line('links_left', firmLinks($p, 'c1'));
    });
    run('link.firm_side_link', function ($p) {
        $p->seed('Account', 'a2'); $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1']]);
        $p->recordLink('Account', 'a2', 'contacts', 'c1');
        line('links_now', firmLinks($p, 'c1'));
    });
    run('link.firm_side_link_audit_unwritable', function ($p) {
        $p->seed('Account', 'a2'); $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1']]); $p->failAudit = true;
        try { $p->recordLink('Account', 'a2', 'contacts', 'c1'); } finally { line('links_after_refused_firm_side_link', firmLinks($p, 'c1')); }
    });
    run('link.branch_link', function ($p) {
        $p->seed('Account', 'p1'); $p->seed('Account', 'b1', ['parentId' => 'p0']);
        $p->recordLink('Account', 'p1', 'branches', 'b1');
        line('parent_now', field($p, 'Account', 'b1', 'parentId'));
    });
    run('link.branch_unlink', function ($p) {
        $p->seed('Account', 'p1'); $p->seed('Account', 'b1', ['parentId' => 'p1']);
        $p->recordUnlink('Account', 'p1', 'branches', 'b1');
        line('parent_now', field($p, 'Account', 'b1', 'parentId') ?: 'none');
    });
    run('link.branch_link_audit_unwritable', function ($p) {
        $p->seed('Account', 'p1'); $p->seed('Account', 'b1', ['parentId' => 'p0']); $p->failAudit = true;
        try { $p->recordLink('Account', 'p1', 'branches', 'b1'); } finally { line('parent_after_refused_link', field($p, 'Account', 'b1', 'parentId')); }
    });
    run('link.branch_unlink_audit_unwritable', function ($p) {
        $p->seed('Account', 'p1'); $p->seed('Account', 'b1', ['parentId' => 'p1']); $p->failAudit = true;
        try { $p->recordUnlink('Account', 'p1', 'branches', 'b1'); } finally { line('parent_after_refused_unlink', field($p, 'Account', 'b1', 'parentId')); }
    });
    run('link.enquiry_link', function ($p) { $p->seed('Account', 'a1'); $p->seed('Opportunity', 'o1', ['accountId' => 'a0']); $p->recordLink('Account', 'a1', 'opportunities', 'o1'); });
    run('link.enquiry_unlink', function ($p) { $p->seed('Account', 'a1'); $p->seed('Opportunity', 'o1', ['accountId' => 'a1']); $p->recordUnlink('Account', 'a1', 'opportunities', 'o1'); });
    run('link.enquiry_link_audit_unwritable', function ($p) {
        $p->seed('Account', 'a1'); $p->seed('Opportunity', 'o1', ['accountId' => 'a0']); $p->failAudit = true;
        try { $p->recordLink('Account', 'a1', 'opportunities', 'o1'); } finally { line('enquiry_firm_after_refused_link', field($p, 'Opportunity', 'o1', 'accountId')); }
    });
    run('link.enquiry_belongs_to_relate', function ($p) { $o = $p->seed('Opportunity', 'o1'); $p->relate($o, 'account', $p->seedOnly('Account', 'a1')); });
    run('link.enquiry_belongs_to_audit_unwritable', function ($p) {
        $o = $p->seed('Opportunity', 'o1'); $p->failAudit = true;
        try { $p->relate($o, 'account', $p->seedOnly('Account', 'a1')); } finally { line('enquiry_firm_after_refused_relate', field($p, 'Opportunity', 'o1', 'accountId') ?: 'none'); }
    });
    run('link.primary_firm_from_firm', function ($p) { $p->seed('Account', 'a1'); $p->seed('Contact', 'c1'); $p->recordLink('Account', 'a1', 'contactsPrimary', 'c1'); });
    run('link.primary_firm_from_firm_audit_unwritable', function ($p) {
        $p->seed('Account', 'a1'); $p->seed('Contact', 'c1', ['accountId' => 'a0']); $p->failAudit = true;
        try { $p->recordLink('Account', 'a1', 'contactsPrimary', 'c1'); } finally { line('primary_after_refused_link', field($p, 'Contact', 'c1', 'accountId')); }
    });
    run('link.record_link_hook_refuses_a_successor_on_its_own', function ($p) { $p->seed('Account', 'a1'); $p->seed('Account', 'a2'); $p->recordLink('Account', 'a1', 'predecessors', 'a2', true); });
    run('link.record_unlink_hook_refuses_a_successor_on_its_own', function ($p) { $p->seed('Contact', 'c1'); $p->seed('Contact', 'c2', ['successorId' => 'c1']); $p->recordUnlink('Contact', 'c1', 'predecessors', 'c2', true); });
    run('link.record_unlink_hook_refuses_the_primary_on_its_own', function ($p) { $p->seed('Account', 'a1'); $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1']]); $p->recordUnlink('Contact', 'c1', 'accounts', 'a1', true); });
    run('link.record_unlink_hook_allows_another_firm_on_its_own', function ($p) { $p->seed('Account', 'a1'); $p->seed('Account', 'a2'); $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1', 'a2']]); $p->recordUnlink('Contact', 'c1', 'accounts', 'a2', true); });
    run('link.successor_link', function ($p) { $p->seed('Account', 'a1'); $p->seed('Account', 'a2'); $p->recordLink('Account', 'a1', 'predecessors', 'a2'); });
    run('link.successor_link_admin', function ($p) { $p->seed('Account', 'a1'); $p->seed('Account', 'a2'); $p->recordLink('Account', 'a1', 'predecessors', 'a2'); }, true);
    run('link.contact_predecessors_unlink', function ($p) { $p->seed('Contact', 'c1'); $p->seed('Contact', 'c2', ['successorId' => 'c1']); $p->recordUnlink('Contact', 'c1', 'predecessors', 'c2'); });
    run('link.successor_orm_relate_is_put_back', function ($p) {
        $a = $p->seed('Account', 'a1'); $p->seed('Account', 'a2', ['successorId' => 'a9']);
        try { $p->relate($a, 'predecessors', $p->load('Account', 'a2')); } finally { line('successor_after_refused_relate', field($p, 'Account', 'a2', 'successorId')); }
    });
    run('link.successor_orm_belongs_to_relate', function ($p) {
        $a = $p->seed('Account', 'a1');
        try { $p->relate($a, 'successor', $p->seedOnly('Account', 'a2')); } finally { line('successor_after', field($p, 'Account', 'a1', 'successorId') ?: 'none'); }
    });
    run('link.other_link_untouched', function ($p) { $a = $p->seed('Account', 'a1'); $p->seed('Account', 'a2'); $p->recordLink('Account', 'a1', 'documents', 'a2'); });
    run('link.orm_unlink_primary_is_put_back', function ($p) {
        // Code that unrelates through the ORM directly (no record hook) is caught by the after hook.
        $p->crmHooks = false;
        $c = $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1']]);
        try { $p->unrelate($c, 'accounts', $p->seedOnly('Account', 'a1')); } finally { line('links_after_orm_unlink', firmLinks($p, 'c1')); }
    });
    run('link.orm_firm_side_unlink_primary_is_put_back_before_the_platform_clears_it', function ($p) {
        // The platform's own Account hook clears a contact's primary firm when it is unlinked from
        // that firm. The identity hook runs first, so the unlink is refused and put back, and the
        // primary firm is never cleared behind the audit's back.
        $a = $p->seed('Account', 'a1');
        $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1']]);
        try { $p->unrelate($a, 'contacts', $p->load('Contact', 'c1')); } finally {
            line('primary_after_orm_firm_side_unlink', field($p, 'Contact', 'c1', 'accountId') ?: 'none');
            line('links_after_orm_firm_side_unlink', firmLinks($p, 'c1'));
        }
    });
    run('link.orm_link_by_identifier', function ($p) {
        $c = $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1']]);
        $p->relate($c, 'accounts', $p->seedOnly('Account', 'a2'));
    });
    run('link.orm_link_audit_unwritable_is_put_back', function ($p) {
        $c = $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1']]); $p->failAudit = true;
        try { $p->relate($c, 'accounts', $p->seedOnly('Account', 'a2')); } finally { line('links_after_refused_orm_link', firmLinks($p, 'c1')); }
    });
    run('link.put_back_cannot_run', function ($p) {
        // R2: with the database refusing every write after the failure, the link is still not committed.
        $c = $p->seed('Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1']]); $p->failAudit = true; $p->failExecutor = true;
        try { $p->relate($c, 'accounts', $p->seedOnly('Account', 'a2')); } finally { line('links_when_put_back_fails', firmLinks($p, 'c1')); }
    });

    // ---- bulk link (the platform refuses it first; this is the after-hook backstop) ----
    run('bulk.Account.contacts', function ($p) {
        $a = $p->seed('Account', 'a1'); $p->seed('Contact', 'c1'); $p->seed('Contact', 'c2');
        try { $p->massRelate($a, 'contacts', 'Contact', ['c1', 'c2']); } finally { line('link_rows_left_after_bulk', $p->linkRows()); }
    });
    run('bulk.Account.branches', fn($p) => $p->massRelate($p->seed('Account', 'a1'), 'branches', 'Account', []));
    run('bulk.Account.opportunities', fn($p) => $p->massRelate($p->seed('Account', 'a1'), 'opportunities', 'Opportunity', []));
    run('bulk.Account.predecessors', fn($p) => $p->massRelate($p->seed('Account', 'a1'), 'predecessors', 'Account', []));
    run('bulk.Contact.accounts', function ($p) {
        $c = $p->seed('Contact', 'c1'); $p->seed('Account', 'a1'); $p->seed('Account', 'a2');
        try { $p->massRelate($c, 'accounts', 'Account', ['a1', 'a2']); } finally { line('link_rows_left_after_bulk_contact', $p->linkRows()); }
    });
    run('bulk.Account.documents', fn($p) => $p->massRelate($p->seed('Account', 'a1'), 'documents', 'Account', []));

    // ---- remove ----
    foreach (['Account', 'Contact'] as $type) {
        run("remove.$type", function ($p) use ($type) { $p->remove($p->seed($type, 'x1')); });
        run("remove.{$type}_admin", function ($p) use ($type) { $p->remove($p->seed($type, 'x1')); }, true);
        run("remove.{$type}_record_route", function ($p) use ($type) {
            $p->seed($type, 'x1');
            try { $p->recordDelete($type, 'x1'); } finally { line("remove_{$type}_rows_left", $p->count($type)); }
        }, true);
    }
    foreach (['Account', 'Contact'] as $type) {
        run("remove.{$type}_record_hook_on_its_own", function ($p) use ($type) { $p->seed($type, 'x1'); $p->recordDelete($type, 'x1', true); }, true);
    }
    run('remove.Opportunity_is_not_an_identity_record', function ($p) { $p->remove($p->seed('Opportunity', 'o1')); });

    // ---- the audit records are protected ----
    run('audit.create_without_option', fn($p) => $p->save(newOf('IdentityAudit')));
    run('audit.create_with_option', fn($p) => $p->save(newOf('IdentityAudit', ['relationship' => 'status', 'recordType' => 'Account', 'recordId' => 'a1', 'previousValue' => '', 'newValue' => 'x']), ['identityAuditWrite' => true]));
    run('audit.create_with_wrong_option_value', fn($p) => $p->save(newOf('IdentityAudit'), ['identityAuditWrite' => 'yes']));
    run('audit.edit', function ($p) { $a = new FakeEntity('IdentityAudit', false); $a->set(['id' => 'i1']); $p->save($a, ['identityAuditWrite' => true]); });
    run('audit.delete', fn($p) => $p->remove((new FakeEntity('IdentityAudit', false))->set(['id' => 'i1'])));
    run('audit.edit_admin', function ($p) { $a = new FakeEntity('IdentityAudit', false); $a->set(['id' => 'i1']); $p->save($a); }, true);
    run('audit.delete_admin', fn($p) => $p->remove((new FakeEntity('IdentityAudit', false))->set(['id' => 'i1'])), true);

    // ---- CRM-IDINT-001R2 -------------------------------------------------------------------
    // S3: no in-request memory of an audit record survives a rolled-back change. A failure after an
    // audited change was written rolls the change and its audit back; the same change made again in the
    // same request must be audited again, not skipped as "already audited".
    run('memory.relation_failed_then_changed_again', function ($p) {
        $c = $p->seed('Contact', 'c1');
        $p->failAuditAfter = 2;   // the link audit is stored, the primary firm audit of the platform's side effect is not
        try {
            $p->relate($c, 'accounts', $p->seedOnly('Account', 'a2'));
        } catch (Forbidden) {
            line('memory.relation.rolled_back', firmLinks($p, 'c1') === '' && $p->audits() === [] ? 'nothing-left' : 'left');
        }
        $p->failAuditAfter = 0;
        $c = $p->load('Contact', 'c1');   // the rolled-back request's in-memory record is not reused
        $p->relate($c, 'accounts', $p->seedOnly('Account', 'a2'));
        line('memory.relation.links_after_second_change', firmLinks($p, 'c1'));
    });
    run('memory.save_failed_then_changed_again', function ($p) {
        $p->seed('Account', 'a1');
        $c = newOf('Contact', ['accountId' => 'a1', 'accountsIds' => ['a1']]);
        $p->failAuditAfter = 2;   // the link audit is stored, the primary firm audit after the save is not
        try {
            $p->save($c);
        } catch (Forbidden) {
            line('memory.save.rolled_back', $p->count('Contact') === 0 && $p->linkRows() === 0 && $p->audits() === [] ? 'nothing-left' : 'left');
        }
        $p->failAuditAfter = 0;
        $p->save($c);
        line('memory.save.links_after_second_change', firmLinks($p, $c->getId()));
    });

    run('create.enquiry_with_firm_audit_unwritable', function ($p) {
        $p->seed('Account', 'a1');
        $p->failAudit = true;
        try {
            apiCreate($p, 'Opportunity', ['accountId' => 'a1']);
        } finally {
            line('enquiries_left_after_failed_create', $p->count('Opportunity'));
        }
    });

    // S4: script functions cannot write these types (the platform's system-write restriction), and a record
    // save carrying a link list only the link routes may change is refused.
    foreach (['Account', 'Contact', 'Opportunity', 'AccountContact', 'Task'] as $type) {
        run("script.may_write.$type", function ($p) use ($type) { line("script_may_write_$type", $p->scriptsMayWrite($type) ? 'yes' : 'no'); });
    }
    run('script.save_with_branches_on_edit', function ($p) { $a = $p->seed('Account', 'a1'); edit($a, ['branchesIds' => ['b1']]); $p->save($a); });
    run('script.save_with_predecessors_on_edit', function ($p) { $a = $p->seed('Account', 'a1'); edit($a, ['predecessorsIds' => ['b1']]); $p->save($a); });
    run('script.save_with_predecessors_on_edit_contact', function ($p) { $c = $p->seed('Contact', 'c1'); edit($c, ['predecessorsIds' => ['b1']]); $p->save($c); });
    run('script.save_with_branches_on_create', fn($p) => $p->save(newOf('Account', ['name' => 'n', 'branchesIds' => ['b1']])));
    run('script.save_with_empty_branches_on_create', fn($p) => $p->save(newOf('Account', ['name' => 'n', 'branchesIds' => []])));

    // S5: enquiry merge is disabled like firm and contact merge.
    foreach (['Account', 'Contact', 'Opportunity'] as $type) {
        run("merge.disabled.$type", function ($p) use ($type) { line("merge_disabled_$type", $p->actionDisabled($type, 'merge') ? 'yes' : 'no'); });
    }
}
