<?php
/**
 * CRM-IDINT-001 test stand-ins for the EspoCRM classes the identity PHP uses.
 * They follow the EspoCRM signatures as understood from the sources the existing
 * hooks use. EspoCRM itself is NOT executed by the unit tests (the operator
 * proof does that); these stubs only let php run the custom code's own logic.
 */

namespace Espo\Core\Exceptions {
    class Forbidden extends \Exception {}
    class BadRequest extends \Exception {}
}

namespace Espo\ORM\Repository\Option {
    class SaveOptions {
        public function __construct(private array $o = []) {}
        public function get(string $n): mixed { return $this->o[$n] ?? null; }
    }
    class RemoveOptions {}
    class RelateOptions {}
    class UnrelateOptions {}
    class MassRelateOptions {}
}

namespace Espo\ORM {
    class Entity {
        public array $f = [];
        public array $fetched = [];
        public function __construct(private string $type, private bool $new) {}
        public function getEntityType(): string { return $this->type; }
        public function isNew(): bool { return $this->new; }
        public function forceNew(): void { $this->new = true; }
        public function markSaved(): void { $this->new = false; $this->fetched = $this->f; }
        public function getId(): ?string { return $this->f['id'] ?? null; }
        public function has(string $n): bool { return array_key_exists($n, $this->f); }
        public function get(string $n): mixed { return $this->f[$n] ?? null; }
        public function set(array|string $a, mixed $v = null): void {
            if (is_array($a)) { foreach ($a as $k => $x) { $this->f[$k] = $x; } } else { $this->f[$a] = $v; }
        }
        public function getFetched(string $n): mixed { return $this->fetched[$n] ?? null; }
        public function isAttributeChanged(string $n): bool {
            $a = $this->f[$n] ?? null;
            $b = $this->fetched[$n] ?? null;
            if (is_array($a) || is_array($b)) { $a = (array) $a; $b = (array) $b; sort($a); sort($b); }
            return $a !== $b;
        }
    }

    class Repo {
        public function __construct(private EntityManager $em, private string $type) {}
        public function deleteFromDb(string $id): void { unset($this->em->store[$this->type][$id]); }
        public function where(array $w): object {
            $rows = array_filter($this->em->store[$this->type] ?? [], function ($e) use ($w) {
                foreach ($w as $k => $v) { if ((string) $e->get($k) !== (string) $v) { return false; } }
                return true;
            });
            return new class(count($rows)) { public function __construct(private int $n) {} public function count(): int { return $this->n; } };
        }
    }

    class QueryExecutor {
        public function __construct(private EntityManager $em) {}
        public function execute(\Espo\ORM\Query\DeleteQuery $q): void {
            if ($this->em->failLinkDelete) { throw new \RuntimeException('cannot delete'); }
            unset($this->em->links[$q->table][$q->where['contactId']]);
        }
    }

    class EntityManager {
        public array $store = [];
        public bool $failAudit = false;
        public bool $lieOnReadBack = false;
        public bool $failLinkDelete = false;
        public int $failAuditAfter = 0;
        private int $auditWrites = 0;
        /** Link rows by junction entity and contact id, as core writes them after a save. */
        public array $links = [];
        private int $seq = 0;

        public function getNewEntity(string $type): Entity { return new Entity($type, true); }

        public function getEntityById(string $type, string $id): ?Entity {
            $e = $this->store[$type][$id] ?? null;
            if ($e && $type === 'IdentityAudit' && $this->lieOnReadBack) {
                $e = clone $e;
                $e->f['newValue'] = 'x';
            }
            return $e;
        }

        public function getQueryExecutor(): QueryExecutor { return new QueryExecutor($this); }

        public function getRDBRepository(string $type): Repo { return new Repo($this, $type); }

        public function saveEntity(Entity $e, array $options = []): void {
            $type = $e->getEntityType();
            if ($type === 'IdentityAudit') {
                (new \Espo\Custom\Hooks\IdentityAudit\ProtectIdentityAudit())
                    ->beforeSave($e, new \Espo\ORM\Repository\Option\SaveOptions($options));
                if ($this->failAudit || ($this->failAuditAfter > 0 && ++$this->auditWrites >= $this->failAuditAfter)) { throw new \RuntimeException('storage unwritable'); }
            }
            if (!$e->has('id')) { $e->set('id', strtolower(substr($type, 0, 1)) . (++$this->seq)); }
            $this->store[$type][$e->getId()] = $e;
            if ($type === 'Contact' && $e->isNew() && $e->has('accountsIds')) {
                $this->links['AccountContact'][$e->getId()] = (array) $e->get('accountsIds');
            }
            $e->markSaved();
        }

        public function seed(string $type, string $id, array $f = []): Entity {
            $e = new Entity($type, true);
            $e->set($f + ['id' => $id]);
            $e->markSaved();
            $this->store[$type][$id] = $e;
            return $e;
        }

        public function audits(): array {
            $out = [];
            foreach ($this->store['IdentityAudit'] ?? [] as $a) {
                $out[] = $a->get('relationship') . ':' . $a->get('recordType') . ':' . $a->get('recordId')
                    . ':' . $a->get('previousValue') . '>' . $a->get('newValue');
            }
            return $out;
        }
    }
}

namespace Espo\Entities {
    class User {
        public function __construct(private bool $admin = false) {}
        public function getId(): string { return 'u1'; }
        public function getUserName(): string { return $this->admin ? 'admin' : 'someone'; }
        public function isAdmin(): bool { return $this->admin; }
    }
}

namespace Espo\Core\Hook\Hook {
    interface BeforeSave {
        public function beforeSave(\Espo\ORM\Entity $entity, \Espo\ORM\Repository\Option\SaveOptions $options): void;
    }
    interface AfterSave {
        public function afterSave(\Espo\ORM\Entity $entity, \Espo\ORM\Repository\Option\SaveOptions $options): void;
    }
    interface BeforeRemove {
        public function beforeRemove(\Espo\ORM\Entity $entity, \Espo\ORM\Repository\Option\RemoveOptions $options): void;
    }
    interface BeforeRelate {
        public function beforeRelate(\Espo\ORM\Entity $entity, string $relationName, \Espo\ORM\Entity $foreignEntity, array $columnData, \Espo\ORM\Repository\Option\RelateOptions $options): void;
    }
    interface BeforeUnrelate {
        public function beforeUnrelate(\Espo\ORM\Entity $entity, string $relationName, \Espo\ORM\Entity $foreignEntity, \Espo\ORM\Repository\Option\UnrelateOptions $options): void;
    }
    interface BeforeMassRelate {
        public function beforeMassRelate(\Espo\ORM\Entity $entity, string $relationName, array $params, \Espo\ORM\Repository\Option\MassRelateOptions $options): void;
    }
}

namespace Espo\ORM\Query {
    class DeleteQuery { public function __construct(public string $table, public array $where) {} }
    class DeleteBuilder {
        private string $table = '';
        private array $where = [];
        public static function create(): self { return new self(); }
        public function from(string $t): self { $this->table = $t; return $this; }
        public function where(array $w): self { $this->where = $w; return $this; }
        public function build(): DeleteQuery { return new DeleteQuery($this->table, $this->where); }
    }
}

namespace Espo\Core\Utils {
    class Metadata {
        public function get(array|string $key, mixed $default = null): mixed {
            if ($key === ['entityDefs', 'Contact', 'fields']) {
                return ['title' => ['type' => 'varchar', 'maxLength' => 255], 'description' => ['type' => 'text'],
                        'sfId' => ['type' => 'varchar', 'maxLength' => 18], 'emailAddress' => ['type' => 'email']];
            }
            if ($key === ['entityDefs', 'Account', 'fields']) {
                return ['name' => ['type' => 'varchar', 'maxLength' => 249], 'sfId' => ['type' => 'varchar', 'maxLength' => 18]];
            }
            return $default;
        }
    }
}

namespace Espo\Modules\Crm\Controllers {
    class Account {}
    class Contact {}
}
