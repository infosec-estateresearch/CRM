<?php
/**
 * CRM-IDINT-001 test harness: runs the real custom PHP (IdentityPolicy,
 * IdentityAuditor, IdentityGuard, the hooks, the merge controllers) against the
 * stand-ins in identity_stubs.php. It prints one line per scenario:
 *   <name>=<outcome>|<audit records written>
 * where outcome is ok, Forbidden or BadRequest and an audit record reads
 * relationship:recordType:recordId:previous>new.
 * Usage: php identity_harness.php <path to custom/Espo/Custom>
 */

namespace {
    require __DIR__ . '/identity_stubs.php';

    use Espo\Core\Exceptions\BadRequest;
    use Espo\Core\Exceptions\Forbidden;
    use Espo\ORM\Entity;
    use Espo\ORM\EntityManager;
    use Espo\ORM\Repository\Option as O;
    use Espo\Custom\Classes\Identity\IdentityPolicy as P;

    $root = $argv[1];
    foreach (['Identity/IdentityPolicy', 'Identity/IdentityAuditor', 'Identity/IdentityGuard'] as $c) {
        require "$root/Classes/$c.php";
    }
    require "$root/Hooks/IdentityAudit/ProtectIdentityAudit.php";
    foreach (['Account', 'Contact', 'Opportunity'] as $e) {
        foreach (glob("$root/Hooks/$e/Identity*.php") as $f) {
            require $f;
        }
    }
    require "$root/Controllers/Account.php";
    require "$root/Controllers/Contact.php";

    function guard(EntityManager $em, bool $admin = false): \Espo\Custom\Classes\Identity\IdentityGuard
    {
        return new \Espo\Custom\Classes\Identity\IdentityGuard(
            $em,
            new \Espo\Custom\Classes\Identity\IdentityAuditor($em, new \Espo\Entities\User($admin)),
            new \Espo\Core\Utils\Metadata()
        );
    }

    function hook(string $entity, string $kind, EntityManager $em, bool $admin = false): object
    {
        $cls = "Espo\\Custom\\Hooks\\$entity\\Identity$kind";

        return new $cls(guard($em, $admin));
    }

    /** Save as EspoCRM does: before hook, insert or update, after hook. */
    function save(EntityManager $em, Entity $e, array $opts = [], bool $admin = false): void
    {
        $o = new O\SaveOptions($opts);
        $t = $e->getEntityType();
        hook($t, 'BeforeSave', $em, $admin)->beforeSave($e, $o);
        $wasNew = $e->isNew();
        $em->saveEntity($e);
        if ($wasNew) {
            // EspoCRM keeps isNew() true until the after-save hooks have run.
            $e->forceNew();
        }
        hook($t, 'AfterSave', $em, $admin)->afterSave($e, $o);
    }

    function relate(EntityManager $em, Entity $e, string $link, Entity $f, bool $on = true, bool $admin = false): void
    {
        $t = $e->getEntityType();
        if ($on) {
            hook($t, 'BeforeRelate', $em, $admin)->beforeRelate($e, $link, $f, [], new O\RelateOptions());
        } else {
            hook($t, 'BeforeUnrelate', $em, $admin)->beforeUnrelate($e, $link, $f, new O\UnrelateOptions());
        }
    }

    function run(string $name, callable $fn): void
    {
        $em = new EntityManager();
        try {
            $fn($em);
            $r = 'ok';
        } catch (Forbidden) {
            $r = 'Forbidden';
        } catch (BadRequest) {
            $r = 'BadRequest';
        }
        echo $name . '=' . $r . '|' . implode(',', $em->audits()) . "\n";
    }

    function seed(EntityManager $em, string $type, string $id, array $f = []): Entity
    {
        return $em->seed($type, $id, $f);
    }

    function edit(Entity $e, array $changes): void
    {
        $e->set($changes);
    }

    function newOf(string $type, array $f = []): Entity
    {
        $e = new Entity($type, true);
        $e->set($f);

        return $e;
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

    // ---- create ----
    run('create.plain_account', fn($em) => save($em, newOf('Account')));
    run('create.supplied_id', fn($em) => save($em, newOf('Account', ['id' => 'chosen'])));
    run('create.supplied_id_contact', fn($em) => save($em, newOf('Contact', ['id' => 'chosen'])));
    run('create.supplied_id_enquiry', fn($em) => save($em, newOf('Opportunity', ['id' => 'chosen'])));
    run('create.supplied_id_admin', fn($em) => save($em, newOf('Account', ['id' => 'chosen']), [], true));
    run('create.import_option', fn($em) => save($em, newOf('Account'), ['import' => true]));
    run('create.with_parent', function ($em) { seed($em, 'Account', 'p1'); save($em, newOf('Account', ['parentId' => 'p1'])); });
    run('create.with_parent_audit_unwritable', function ($em) {
        seed($em, 'Account', 'p1');
        $em->failAudit = true;
        try {
            save($em, newOf('Account', ['parentId' => 'p1']));
        } finally {
            echo 'accounts_left=' . count($em->store['Account']) . "\n";
        }
    });
    run('create.contact_with_primary', function ($em) { seed($em, 'Account', 'a1'); save($em, newOf('Contact', ['accountId' => 'a1'])); });
    run('create.enquiry_with_firm', function ($em) { seed($em, 'Account', 'a1'); save($em, newOf('Opportunity', ['accountId' => 'a1'])); });
    run('create.contact_primary_not_linked', fn($em) => save($em, newOf('Contact', ['accountId' => 'a1', 'accountsIds' => ['a2']])));
    run('create.contact_primary_linked', fn($em) => save($em, newOf('Contact', ['accountId' => 'a1', 'accountsIds' => ['a1', 'a2']])));
    run('create.contact_with_links', function ($em) { save($em, newOf('Contact', ['accountId' => 'a1', 'accountsIds' => ['a1', 'a2']])); });
    run('create.contact_links_without_primary', function ($em) { save($em, newOf('Contact', ['accountsIds' => ['a1', 'a2']])); });
    run('create.contact_links_duplicate_ids', function ($em) { save($em, newOf('Contact', ['accountsIds' => ['a1', 'a1']])); });
    run('create.contact_links_then_core_fires_relate', function ($em) {
        // Core may also fire beforeRelate for each link while it writes the rows: no double record.
        $c = newOf('Contact', ['accountsIds' => ['a1', 'a2']]);
        save($em, $c);
        $c->forceNew();
        relate($em, $c, 'accounts', seed($em, 'Account', 'a1'));
        relate($em, $c, 'accounts', seed($em, 'Account', 'a2'));
    });
    run('create.contact_links_relate_fires_before_after_save', function ($em) {
        $c = newOf('Contact', ['accountsIds' => ['a1']]);
        $o = new O\SaveOptions([]);
        hook('Contact', 'BeforeSave', $em)->beforeSave($c, $o);
        $em->saveEntity($c);
        $c->forceNew();
        relate($em, $c, 'accounts', seed($em, 'Account', 'a1'));
        hook('Contact', 'AfterSave', $em)->afterSave($c, $o);
    });
    run('create.contact_links_audit_unwritable', function ($em) {
        $em->failAudit = true;
        try {
            save($em, newOf('Contact', ['accountsIds' => ['a1', 'a2']]));
        } finally {
            echo 'link_create_contacts_left=' . count($em->store['Contact'] ?? []) . "\n";
            echo 'link_create_link_rows_left=' . count($em->links['AccountContact'] ?? []) . "\n";
        }
    });
    run('create.contact_links_audit_fails_on_second_link', function ($em) {
        // The first link is audited, the store then fails: the create is undone, links and all.
        $em->failAuditAfter = 2;
        try {
            save($em, newOf('Contact', ['accountsIds' => ['a1', 'a2']]));
        } finally {
            echo 'link_create2_contacts_left=' . count($em->store['Contact'] ?? []) . "\n";
            echo 'link_create2_link_rows_left=' . count($em->links['AccountContact'] ?? []) . "\n";
        }
    });
    run('create.contact_links_undo_cannot_delete_link_rows', function ($em) {
        $em->failAudit = true;
        $em->failLinkDelete = true;
        try {
            save($em, newOf('Contact', ['accountsIds' => ['a1']]));
        } finally {
            echo 'link_undo_fail_contacts_left=' . count($em->store['Contact'] ?? []) . "\n";
            echo 'link_undo_fail_link_rows_left=' . count($em->links['AccountContact'] ?? []) . "\n";
        }
    });
    run('create.retired_new', fn($em) => save($em, newOf('Account', ['identityStatus' => 'retired'])));
    run('create.successor_new', function ($em) { seed($em, 'Account', 'a1'); save($em, newOf('Account', ['identityStatus' => 'superseded', 'successorId' => 'a1'])); });

    // ---- edit ----
    run('edit.parent_change', function ($em) { $a = seed($em, 'Account', 'a1', ['parentId' => 'p1']); edit($a, ['parentId' => 'p2']); save($em, $a); });
    run('edit.parent_clear', function ($em) { $a = seed($em, 'Account', 'a1', ['parentId' => 'p1']); edit($a, ['parentId' => null]); save($em, $a); });
    run('edit.parent_same_value', function ($em) { $a = seed($em, 'Account', 'a1', ['parentId' => 'p1']); edit($a, ['parentId' => 'p1']); save($em, $a); });
    run('edit.parent_audit_unwritable', function ($em) { $a = seed($em, 'Account', 'a1', ['parentId' => 'p1']); $em->failAudit = true; edit($a, ['parentId' => 'p2']); save($em, $a); });
    run('edit.parent_audit_readback_differs', function ($em) { $a = seed($em, 'Account', 'a1', ['parentId' => 'p1']); $em->lieOnReadBack = true; edit($a, ['parentId' => 'p2']); save($em, $a); });
    run('edit.parent_admin', function ($em) { $a = seed($em, 'Account', 'a1', ['parentId' => 'p1']); edit($a, ['parentId' => 'p2']); save($em, $a, [], true); });
    run('edit.unrelated_field', function ($em) { $a = seed($em, 'Account', 'a1'); edit($a, ['name' => 'x']); save($em, $a); });
    run('edit.contact_primary', function ($em) { $c = seed($em, 'Contact', 'c1', ['accountId' => 'a1']); edit($c, ['accountId' => 'a2']); save($em, $c); });
    run('edit.contact_primary_clear', function ($em) { $c = seed($em, 'Contact', 'c1', ['accountId' => 'a1']); edit($c, ['accountId' => null]); save($em, $c); });
    run('edit.contact_drops_primary_link', function ($em) { $c = seed($em, 'Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1', 'a2']]); edit($c, ['accountsIds' => ['a2']]); save($em, $c); });
    run('edit.contact_moves_primary_and_link', function ($em) { $c = seed($em, 'Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1', 'a2']]); edit($c, ['accountId' => 'a2', 'accountsIds' => ['a2']]); save($em, $c); });
    run('edit.contact_clears_primary_and_link', function ($em) { $c = seed($em, 'Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1', 'a2']]); edit($c, ['accountId' => null, 'accountsIds' => ['a2']]); save($em, $c); });
    run('edit.contact_adds_link', function ($em) { $c = seed($em, 'Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a1']]); edit($c, ['accountsIds' => ['a1', 'a3']]); save($em, $c); });
    run('edit.enquiry_firm', function ($em) { $o = seed($em, 'Opportunity', 'o1', ['accountId' => 'a1']); edit($o, ['accountId' => 'a2']); save($em, $o); });
    run('edit.enquiry_firm_audit_unwritable', function ($em) { $o = seed($em, 'Opportunity', 'o1', ['accountId' => 'a1']); $em->failAudit = true; edit($o, ['accountId' => 'a2']); save($em, $o); });
    run('edit.exception_primary_unlinked_then_other_edit', function ($em) {
        // An existing exception (primary not among the links) can still be edited for other reasons.
        $c = seed($em, 'Contact', 'c1', ['accountId' => 'a1', 'accountsIds' => ['a2']]);
        edit($c, ['title' => 'x']);
        save($em, $c);
    });

    // ---- over-length input ----
    run('length.title_at_limit', fn($em) => save($em, newOf('Contact', ['title' => str_repeat('a', 255)])));
    run('length.title_over_limit', fn($em) => save($em, newOf('Contact', ['title' => str_repeat('a', 256)])));
    run('length.title_over_limit_multibyte', fn($em) => save($em, newOf('Contact', ['title' => str_repeat("\u{e9}", 256)])));
    run('length.title_multibyte_at_limit', fn($em) => save($em, newOf('Contact', ['title' => str_repeat("\u{e9}", 255)])));
    run('length.account_name_over_limit', fn($em) => save($em, newOf('Account', ['name' => str_repeat('a', 250)])));
    run('length.title_over_limit_on_edit', function ($em) { $c = seed($em, 'Contact', 'c1'); edit($c, ['title' => str_repeat('a', 300)]); save($em, $c); });
    run('length.legacy_long_value_untouched_on_other_edit', function ($em) { $c = seed($em, 'Contact', 'c1', ['title' => str_repeat('a', 300)]); edit($c, ['description' => 'x']); save($em, $c); });
    run('length.nothing_stored_when_refused', function ($em) {
        try { save($em, newOf('Contact', ['title' => str_repeat('a', 256)])); } finally { echo 'contacts_stored=' . count($em->store['Contact'] ?? []) . "\n"; }
    });

    // ---- retire and supersede ----
    run('status.retire', function ($em) { $a = seed($em, 'Account', 'a1'); edit($a, ['identityStatus' => 'retired']); save($em, $a); });
    run('status.retire_contact', function ($em) { $a = seed($em, 'Contact', 'c1'); edit($a, ['identityStatus' => 'retired']); save($em, $a); });
    run('status.supersede', function ($em) { $a = seed($em, 'Account', 'a1'); seed($em, 'Account', 'a2'); edit($a, ['identityStatus' => 'superseded', 'successorId' => 'a2']); save($em, $a); });
    run('status.supersede_contact', function ($em) { $a = seed($em, 'Contact', 'c1'); seed($em, 'Contact', 'c2'); edit($a, ['identityStatus' => 'superseded', 'successorId' => 'c2']); save($em, $a); });
    run('status.supersede_self', function ($em) { $a = seed($em, 'Account', 'a1'); edit($a, ['identityStatus' => 'superseded', 'successorId' => 'a1']); save($em, $a); });
    run('status.supersede_missing', function ($em) { $a = seed($em, 'Account', 'a1'); edit($a, ['identityStatus' => 'superseded', 'successorId' => 'nope']); save($em, $a); });
    run('status.supersede_wrong_kind', function ($em) { $a = seed($em, 'Account', 'a1'); seed($em, 'Contact', 'c9'); edit($a, ['identityStatus' => 'superseded', 'successorId' => 'c9']); save($em, $a); });
    run('status.supersede_cycle', function ($em) { seed($em, 'Account', 'a2', ['identityStatus' => 'superseded', 'successorId' => 'a1']); $a = seed($em, 'Account', 'a1'); edit($a, ['identityStatus' => 'superseded', 'successorId' => 'a2']); save($em, $a); });
    run('status.supersede_long_cycle', function ($em) { seed($em, 'Account', 'a3', ['identityStatus' => 'superseded', 'successorId' => 'a1']); seed($em, 'Account', 'a2', ['identityStatus' => 'superseded', 'successorId' => 'a3']); $a = seed($em, 'Account', 'a1'); edit($a, ['identityStatus' => 'superseded', 'successorId' => 'a2']); save($em, $a); });
    run('status.supersede_into_a_chain', function ($em) { seed($em, 'Account', 'a3'); seed($em, 'Account', 'a2', ['identityStatus' => 'superseded', 'successorId' => 'a3']); $a = seed($em, 'Account', 'a1'); edit($a, ['identityStatus' => 'superseded', 'successorId' => 'a2']); save($em, $a); });
    run('status.superseded_without_successor', function ($em) { $a = seed($em, 'Account', 'a1'); edit($a, ['identityStatus' => 'superseded']); save($em, $a); });
    run('status.retired_with_successor', function ($em) { $a = seed($em, 'Account', 'a1'); seed($em, 'Account', 'a2'); edit($a, ['identityStatus' => 'retired', 'successorId' => 'a2']); save($em, $a); });
    run('status.active_with_successor', function ($em) { $a = seed($em, 'Account', 'a1'); seed($em, 'Account', 'a2'); edit($a, ['successorId' => 'a2']); save($em, $a); });
    run('status.unknown_value', function ($em) { $a = seed($em, 'Account', 'a1'); edit($a, ['identityStatus' => 'deleted']); save($em, $a); });
    run('status.reactivate', function ($em) { $a = seed($em, 'Account', 'a1', ['identityStatus' => 'retired']); edit($a, ['identityStatus' => 'active']); save($em, $a); });
    run('status.audit_unwritable', function ($em) { $a = seed($em, 'Account', 'a1'); $em->failAudit = true; edit($a, ['identityStatus' => 'retired']); save($em, $a); });

    // ---- links ----
    run('link.contact_unlink_primary', function ($em) { $c = seed($em, 'Contact', 'c1', ['accountId' => 'a1']); relate($em, $c, 'accounts', seed($em, 'Account', 'a1'), false); });
    run('link.contact_unlink_primary_admin', function ($em) { $c = seed($em, 'Contact', 'c1', ['accountId' => 'a1']); relate($em, $c, 'accounts', seed($em, 'Account', 'a1'), false, true); });
    run('link.contact_unlink_other', function ($em) { $c = seed($em, 'Contact', 'c1', ['accountId' => 'a1']); relate($em, $c, 'accounts', seed($em, 'Account', 'a2'), false); });
    run('link.contact_link', function ($em) { $c = seed($em, 'Contact', 'c1', ['accountId' => 'a1']); relate($em, $c, 'accounts', seed($em, 'Account', 'a2')); });
    run('link.contact_link_audit_unwritable', function ($em) { $c = seed($em, 'Contact', 'c1'); $em->failAudit = true; relate($em, $c, 'accounts', seed($em, 'Account', 'a2')); });
    run('link.firm_side_unlink_primary', function ($em) { $a = seed($em, 'Account', 'a1'); relate($em, $a, 'contacts', seed($em, 'Contact', 'c1', ['accountId' => 'a1']), false); });
    run('link.firm_side_unlink_other', function ($em) { $a = seed($em, 'Account', 'a2'); relate($em, $a, 'contacts', seed($em, 'Contact', 'c1', ['accountId' => 'a1']), false); });
    run('link.firm_side_link', function ($em) { $a = seed($em, 'Account', 'a2'); relate($em, $a, 'contacts', seed($em, 'Contact', 'c1', ['accountId' => 'a1'])); });
    run('link.branch_link', function ($em) { $p = seed($em, 'Account', 'p1'); relate($em, $p, 'branches', seed($em, 'Account', 'b1', ['parentId' => 'p0'])); });
    run('link.branch_unlink', function ($em) { $p = seed($em, 'Account', 'p1'); relate($em, $p, 'branches', seed($em, 'Account', 'b1', ['parentId' => 'p1']), false); });
    run('link.parent_unlink_from_child', function ($em) { $b = seed($em, 'Account', 'b1', ['parentId' => 'p1']); relate($em, $b, 'parent', seed($em, 'Account', 'p1'), false); });
    run('link.branch_link_audit_unwritable', function ($em) { $p = seed($em, 'Account', 'p1'); $em->failAudit = true; relate($em, $p, 'branches', seed($em, 'Account', 'b1')); });
    run('link.enquiry_link', function ($em) { $a = seed($em, 'Account', 'a1'); relate($em, $a, 'opportunities', seed($em, 'Opportunity', 'o1', ['accountId' => 'a0'])); });
    run('link.enquiry_unlink', function ($em) { $a = seed($em, 'Account', 'a1'); relate($em, $a, 'opportunities', seed($em, 'Opportunity', 'o1', ['accountId' => 'a1']), false); });
    run('link.enquiry_side_link', function ($em) { $o = seed($em, 'Opportunity', 'o1'); relate($em, $o, 'account', seed($em, 'Account', 'a1')); });
    run('link.primary_firm_from_firm', function ($em) { $a = seed($em, 'Account', 'a1'); relate($em, $a, 'contactsPrimary', seed($em, 'Contact', 'c1')); });
    run('link.successor_link', function ($em) { $a = seed($em, 'Account', 'a1'); relate($em, $a, 'successor', seed($em, 'Account', 'a2')); });
    run('link.predecessors_link', function ($em) { $a = seed($em, 'Account', 'a1'); relate($em, $a, 'predecessors', seed($em, 'Account', 'a2')); });
    run('link.contact_successor_unlink', function ($em) { $c = seed($em, 'Contact', 'c1'); relate($em, $c, 'successor', seed($em, 'Contact', 'c2'), false); });
    run('link.other_link_untouched', function ($em) { $a = seed($em, 'Account', 'a1'); relate($em, $a, 'documents', seed($em, 'Account', 'a2')); });
    run('link.new_record_audit_unwritable_is_undone', function ($em) {
        $c = newOf('Contact', ['id' => 'c9']);
        $em->store['Contact']['c9'] = $c;
        $em->failAudit = true;
        try {
            relate($em, $c, 'accounts', seed($em, 'Account', 'a2'));
        } finally {
            echo 'contacts_left=' . count($em->store['Contact'] ?? []) . "\n";
        }
    });

    // ---- bulk link ----
    foreach ([
        'Account' => ['branches', 'contacts', 'contactsPrimary', 'opportunities', 'parent', 'predecessors', 'documents'],
        'Contact' => ['accounts', 'account', 'predecessors', 'opportunities'],
    ] as $type => $links) {
        foreach ($links as $link) {
            run("bulk.$type.$link", function ($em) use ($type, $link) {
                hook($type, 'BeforeMassRelate', $em)->beforeMassRelate(seed($em, $type, 'x1'), $link, [], new O\MassRelateOptions());
            });
        }
    }

    // ---- remove ----
    foreach (['Account', 'Contact'] as $type) {
        run("remove.$type", fn($em) => hook($type, 'BeforeRemove', $em)->beforeRemove(seed($em, $type, 'x1'), new O\RemoveOptions()));
        run("remove.{$type}_admin", fn($em) => hook($type, 'BeforeRemove', $em, true)->beforeRemove(seed($em, $type, 'x1'), new O\RemoveOptions()));
    }

    // ---- merge ----
    foreach (['Account', 'Contact'] as $type) {
        $cls = "Espo\\Custom\\Controllers\\$type";
        run("merge.$type", fn($em) => (new $cls())->postActionMerge(new stdClass(), new stdClass()));
        run("merge.{$type}_no_args", fn($em) => (new $cls())->postActionMerge());
    }

    // ---- the audit records are protected ----
    $protect = new Espo\Custom\Hooks\IdentityAudit\ProtectIdentityAudit();
    run('audit.create_without_option', fn($em) => $protect->beforeSave(newOf('IdentityAudit'), new O\SaveOptions([])));
    run('audit.create_with_option', fn($em) => $protect->beforeSave(newOf('IdentityAudit'), new O\SaveOptions(['identityAuditWrite' => true])));
    run('audit.create_with_wrong_option_value', fn($em) => $protect->beforeSave(newOf('IdentityAudit'), new O\SaveOptions(['identityAuditWrite' => 'yes'])));
    run('audit.edit', fn($em) => $protect->beforeSave($em->seed('IdentityAudit', 'i1'), new O\SaveOptions(['identityAuditWrite' => true])));
    run('audit.delete', fn($em) => $protect->beforeRemove($em->seed('IdentityAudit', 'i1'), new O\RemoveOptions()));
}
