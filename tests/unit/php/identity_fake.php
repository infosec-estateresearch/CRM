<?php
/**
 * CRM-IDINT-001R: a small fake of the EspoCRM persistence layer, in the CrmTest namespace.
 *
 * It exists to run the custom identity PHP in the order the platform runs it, using the
 * platform's REAL hook interfaces, option classes and GeneralInvoker (loaded from the pinned
 * reference). It copies what the reference does and nothing it does not:
 * - the identifier of a new record is assigned before the before-save hooks run
 *   (Core/Repositories/Database.php, prepareSaveInternal);
 * - hooks run in order of their static $order, 9 by default (Core/HookManager);
 * - relation hooks are AFTER hooks only (Core/ORM/Repository/HookMediator);
 * - the relation is changed by the mapper first (ORM/Mapper/BaseMapper: a junction row, or
 *   a foreign key on the foreign record, or on the record itself), then the hook runs;
 * - the record link route runs the record link hooks, then relates (Core/Record/Service.php, link);
 * - link-multiple values are saved by relating and unrelating (LinkMultipleSaver);
 * - the platform's own Contact hook (Modules/Crm/Hooks/Contact/Accounts) is reproduced in
 *   reduced form because it changes the primary firm and the links as a side effect.
 */

namespace CrmTest {
    use Espo\Core\Hook\GeneralInvoker;
    use Espo\ORM\Entity;
    use Espo\ORM\Query\Delete;
    use Espo\ORM\Query\Query;
    use Espo\ORM\Query\Select;
    use Espo\ORM\Query\Update;

    class FakeEntity implements Entity
    {
        public array $f = [];
        public array $fetched = [];
        private bool $new;

        public function __construct(private string $type, bool $new = true)
        {
            $this->new = $new;
        }

        public function getEntityType(): string
        {
            return $this->type;
        }

        public function isNew(): bool
        {
            return $this->new;
        }

        public function setAsNotNew(): void
        {
            $this->new = false;
            $this->fetched = $this->f;
        }

        public function getId(): string
        {
            return (string) ($this->f['id'] ?? '');
        }

        public function has(string $attribute): bool
        {
            return array_key_exists($attribute, $this->f);
        }

        public function get(string $attribute)
        {
            return $this->f[$attribute] ?? null;
        }

        public function set($attribute, $value = null): static
        {
            if (is_array($attribute)) {
                foreach ($attribute as $k => $v) {
                    $this->f[$k] = $v;
                }
            } else {
                $this->f[$attribute] = $value;
            }

            return $this;
        }

        public function getFetched(string $attribute)
        {
            return $this->fetched[$attribute] ?? null;
        }

        public function isAttributeChanged(string $name): bool
        {
            $a = $this->f[$name] ?? null;
            $b = $this->fetched[$name] ?? null;

            if (is_array($a) || is_array($b)) {
                $a = array_map('strval', (array) $a);
                $b = array_map('strval', (array) $b);
                sort($a);
                sort($b);
            }

            return $a !== $b;
        }
    }

    class FakeUser extends \Espo\Entities\User
    {
        public function __construct(private bool $admin = false)
        {}

        public function getId(): string
        {
            return 'u1';
        }

        public function getUserName(): ?string
        {
            return $this->admin ? 'admin' : 'someone';
        }
    }

    class FakeMetadata extends \Espo\Core\Utils\Metadata
    {
        public function __construct()
        {}

        public function get($key = null, $default = null)
        {
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

    class FakeSelectBuilder extends \Espo\ORM\Repository\RDBSelectBuilder
    {
        public function __construct(private FakePlatform $platform, private Select $query)
        {}

        public function find(): \Espo\ORM\EntityCollection|\Espo\ORM\SthCollection
        {
            return new \Espo\ORM\EntityCollection($this->platform->selectAll($this->query));
        }
    }

    class FakeRepository extends \Espo\ORM\Repository\RDBRepository
    {
        public function __construct(private FakePlatform $platform)
        {}

        public function clone(Select $query): \Espo\ORM\Repository\RDBSelectBuilder
        {
            return new FakeSelectBuilder($this->platform, $query);
        }
    }

    class FakeExecutor implements \Espo\ORM\Executor\QueryExecutor
    {
        public function __construct(private FakePlatform $platform)
        {}

        public function execute(Query $query): \PDOStatement
        {
            $this->platform->executeQuery($query);

            return new \PDOStatement();
        }
    }

    /** The persistence layer: rows, link rows, hooks and the audit store, with failure switches. */
    class FakePlatform extends \Espo\ORM\EntityManager
    {
        public const LINK_DEFS = [
            'Account' => [
                'branches' => ['hasMany', 'Account', 'parentId'],
                'parent' => ['belongsTo', 'Account', 'parentId'],
                'contacts' => ['manyMany', 'Contact', null],
                'contactsPrimary' => ['hasMany', 'Contact', 'accountId'],
                'opportunities' => ['hasMany', 'Opportunity', 'accountId'],
                'successor' => ['belongsTo', 'Account', 'successorId'],
                'predecessors' => ['hasMany', 'Account', 'successorId'],
                'documents' => ['hasMany', 'Account', 'documentOwnerId'],
            ],
            'Contact' => [
                'accounts' => ['manyMany', 'Account', null],
                'account' => ['belongsTo', 'Account', 'accountId'],
                'successor' => ['belongsTo', 'Contact', 'successorId'],
                'predecessors' => ['hasMany', 'Contact', 'successorId'],
                'opportunities' => ['hasMany', 'Opportunity', 'contactLinkOwnerId'],
            ],
            'Opportunity' => [
                'account' => ['belongsTo', 'Account', 'accountId'],
            ],
        ];

        /** @var array<string, array<string, array>> */
        public array $rows = [];
        /** @var list<array{accountId: string, contactId: string, deleted: bool, role: ?string}> */
        public array $junction = [];
        public bool $failAudit = false;
        public bool $lieOnReadBack = false;
        public int $failAuditAfter = 0;
        public bool $failExecutor = false;
        private int $auditWrites = 0;
        private int $seq = 0;
        public array $log = [];
        public bool $crmHooks = true;

        private FakeUser $user;
        private GeneralInvoker $invoker;
        private array $hookCache = [];
        private string $customDir;

        public function __construct(string $customDir, bool $admin = false)
        {
            $this->customDir = $customDir;
            call_user_func(['\\Espo\\Custom\\Classes\\Identity\\IdentityGuard', 'resetRequestState']);
            $this->user = new FakeUser($admin);
            $this->invoker = new GeneralInvoker();
        }

        public function guard(): \Espo\Custom\Classes\Identity\IdentityGuard
        {
            return new \Espo\Custom\Classes\Identity\IdentityGuard(
                $this,
                new \Espo\Custom\Classes\Identity\IdentityAuditor($this, $this->user),
                new FakeMetadata()
            );
        }

        // ---- the part of EntityManager the custom code uses ----------------------------------

        public function getNewEntity(string $entityType): Entity
        {
            return new FakeEntity($entityType, true);
        }

        public function getEntityById(string $entityType, string $id): ?Entity
        {
            return $this->load($entityType, $id);
        }

        public function getQueryExecutor(): \Espo\ORM\Executor\QueryExecutor
        {
            return new FakeExecutor($this);
        }

        public function getRDBRepository(string $entityType): \Espo\ORM\Repository\RDBRepository
        {
            return new FakeRepository($this);
        }

        public function saveEntity(Entity $entity, array $options = []): void
        {
            $this->save($entity, $options);
        }

        // ---- fixtures -------------------------------------------------------------------------

        public function seed(string $type, string $id, array $f = []): FakeEntity
        {
            $links = null;

            if ($type === 'Contact' && array_key_exists('accountsIds', $f)) {
                $links = (array) $f['accountsIds'];
                unset($f['accountsIds']);
            }

            $this->rows[$type][$id] = $f + ['id' => $id];

            foreach ($links ?? [] as $firmId) {
                $this->junction[] = ['accountId' => (string) $firmId, 'contactId' => $id, 'deleted' => false, 'role' => null];
            }

            return $this->load($type, $id);
        }

        public function load(string $type, string $id): ?FakeEntity
        {
            if (!isset($this->rows[$type][$id])) {
                return null;
            }

            $e = new FakeEntity($type, false);
            $e->f = $this->rows[$type][$id];

            if ($type === 'Contact') {
                $e->f['accountsIds'] = $this->linkedFirms($id);
            }

            $e->fetched = $e->f;

            return $e;
        }

        /** An entity as the platform builds it for relate-by-identifier: only the identifier is known. */
        public function seedOnly(string $type, string $id): FakeEntity
        {
            $e = new FakeEntity($type, false);
            $e->f = ['id' => $id];
            $e->fetched = $e->f;

            return $e;
        }

        public function linkedFirms(string $contactId): array
        {
            $out = [];

            foreach ($this->junction as $row) {
                if ($row['contactId'] === $contactId && !$row['deleted']) {
                    $out[] = $row['accountId'];
                }
            }

            return $out;
        }

        public function linkRows(): int
        {
            return count(array_filter($this->junction, fn($r) => !$r['deleted']));
        }

        public function count(string $type): int
        {
            return count($this->rows[$type] ?? []);
        }

        public function audits(): array
        {
            $out = [];

            foreach ($this->rows['IdentityAudit'] ?? [] as $a) {
                $out[] = $a['relationship'] . ':' . $a['recordType'] . ':' . $a['recordId'] . ':' .
                    $a['previousValue'] . '>' . $a['newValue'];
            }

            return $out;
        }

        // ---- hooks ----------------------------------------------------------------------------

        /** @return list<object> hooks of a scope that have the hook method, ordered like HookManager */
        private function hooks(string $scope, string $name): array
        {
            $key = "$scope/$name";

            if (isset($this->hookCache[$key])) {
                return $this->hookCache[$key];
            }

            $list = [];
            $dir = $this->customDir . '/Hooks/' . $scope;

            foreach (glob($dir . '/{Identity,Protect}*.php', GLOB_BRACE) ?: [] as $file) {
                $class = 'Espo\\Custom\\Hooks\\' . $scope . '\\' . basename($file, '.php');

                if (!class_exists($class) || !method_exists($class, $name)) {
                    continue;
                }

                $constructor = (new \ReflectionClass($class))->getConstructor();
                $hook = $constructor ? new $class($this->guard()) : new $class();
                $list[] = [$class::$order ?? 9, $hook];
            }

            usort($list, fn($a, $b) => $a[0] <=> $b[0]);

            return $this->hookCache[$key] = array_map(fn($x) => $x[1], $list);
        }

        private function runHooks(string $scope, string $name, Entity $subject, array $options, array $data = []): void
        {
            $order = [];

            foreach ($this->hooks($scope, $name) as $hook) {
                $order[] = [($hook::$order ?? 9), $hook];
            }

            if ($this->crmHooks && $scope === 'Contact') {
                $order[] = [9, new CrmContactHook($this)];
            }

            if ($this->crmHooks && $scope === 'Account') {
                $order[] = [9, new CrmAccountHook($this)];
            }

            usort($order, fn($a, $b) => $a[0] <=> $b[0]);

            foreach ($order as [, $hook]) {
                if ($hook instanceof CrmContactHook || $hook instanceof CrmAccountHook) {
                    $hook->run($name, $subject, $options, $data);

                    continue;
                }

                $this->invoker->invoke($hook, $name, $subject, $options, $data);
            }
        }

        // ---- saving ----------------------------------------------------------------------------

        public function save(Entity $entity, array $options = []): void
        {
            /** @var FakeEntity $entity */
            $type = $entity->getEntityType();

            if ($type === 'IdentityAudit') {
                $this->saveAudit($entity, $options);

                return;
            }

            if ($entity->isNew() && !$entity->has('id')) {
                $entity->set('id', strtolower(substr($type, 0, 1)) . (++$this->seq));
            }

            $this->runHooks($type, 'beforeSave', $entity, $options);

            $row = $entity->f;
            unset($row['accountsIds']);
            $this->rows[$type][$entity->getId()] = $row;

            if ($type === 'Contact' && $entity->has('accountsIds') && $entity->isAttributeChanged('accountsIds')) {
                $this->saveLinkMultiple($entity, $options);
            }

            $this->runHooks($type, 'afterSave', $entity, $options);

            if ($entity->isNew() && empty($options['keepNew'])) {
                $entity->setAsNotNew();
            } elseif (!$entity->isNew()) {
                $entity->fetched = $entity->f;
            }
        }

        private function saveAudit(FakeEntity $audit, array $options): void
        {
            $this->runHooks('IdentityAudit', 'beforeSave', $audit, $options);

            if ($this->failAudit || ($this->failAuditAfter > 0 && ++$this->auditWrites >= $this->failAuditAfter)) {
                throw new \RuntimeException('storage unwritable');
            }

            if (!$audit->has('id')) {
                $audit->set('id', 'i' . (++$this->seq));
            }

            $row = $audit->f;

            if ($this->lieOnReadBack) {
                $row['newValue'] = 'x';
            }

            $this->rows['IdentityAudit'][$audit->getId()] = $row;
            $audit->setAsNotNew();
        }

        /** LinkMultipleSaver: relate what is added, unrelate what is gone (hooks run each time). */
        private function saveLinkMultiple(FakeEntity $contact, array $options): void
        {
            $specified = array_values(array_unique(array_map('strval', (array) $contact->get('accountsIds'))));
            $existing = $this->linkedFirms($contact->getId());

            foreach ($specified as $id) {
                if (!in_array($id, $existing, true)) {
                    $this->relate($contact, 'accounts', $this->seedOnly('Account', $id), $options);
                }
            }

            if (!$contact->isNew()) {
                foreach ($existing as $id) {
                    if (!in_array($id, $specified, true)) {
                        $this->unrelate($contact, 'accounts', $this->seedOnly('Account', $id), $options);
                    }
                }
            }
        }

        // ---- relations (mapper, then the after hook) -------------------------------------------

        public function relate(Entity $entity, string $link, Entity $foreign, array $options = []): void
        {
            $this->mapper($entity, $link, $foreign, true);
            $this->runHooks($entity->getEntityType(), 'afterRelate', $entity, $options, [
                'relationName' => $link, 'foreignEntity' => $foreign, 'foreignId' => $foreign->getId(), 'relationData' => [],
            ]);
        }

        public function unrelate(Entity $entity, string $link, Entity $foreign, array $options = []): void
        {
            $this->mapper($entity, $link, $foreign, false);
            $this->runHooks($entity->getEntityType(), 'afterUnrelate', $entity, $options, [
                'relationName' => $link, 'foreignEntity' => $foreign, 'foreignId' => $foreign->getId(),
            ]);
        }

        public function massRelate(Entity $entity, string $link, string $foreignType, array $ids, array $options = []): void
        {
            foreach ($ids as $id) {
                $this->mapper($entity, $link, $this->seedOnly($foreignType, $id), true);
            }

            $query = (new \Espo\ORM\Query\SelectBuilder())->from($foreignType)->where(['id' => $ids])->build();
            $this->runHooks($entity->getEntityType(), 'afterMassRelate', $entity, $options, [
                'relationName' => $link, 'query' => $query,
            ]);
        }

        private function mapper(Entity $entity, string $link, Entity $foreign, bool $relate): void
        {
            $type = $entity->getEntityType();
            $def = FakePlatform::LINK_DEFS[$type][$link] ?? null;

            if ($def === null) {
                return;
            }

            [$kind, $foreignType, $fk] = $def;

            if ($kind === 'manyMany') {
                $account = $type === 'Account' ? $entity->getId() : $foreign->getId();
                $contact = $type === 'Contact' ? $entity->getId() : $foreign->getId();

                foreach ($this->junction as &$row) {
                    if ($row['accountId'] === $account && $row['contactId'] === $contact) {
                        $row['deleted'] = !$relate;
                        $found = true;
                    }
                }

                unset($row);

                if ($relate && empty($found)) {
                    $this->junction[] = ['accountId' => $account, 'contactId' => $contact, 'deleted' => false, 'role' => null];
                }

                return;
            }

            if ($kind === 'hasMany') {
                if (!isset($this->rows[$foreignType][$foreign->getId()])) {
                    return;
                }

                if ($relate) {
                    $this->rows[$foreignType][$foreign->getId()][$fk] = $entity->getId();
                } elseif (($this->rows[$foreignType][$foreign->getId()][$fk] ?? null) === $entity->getId()) {
                    $this->rows[$foreignType][$foreign->getId()][$fk] = null;
                }

                return;
            }

            // belongsTo: the mapper writes the key and also sets it, as fetched, on the record in hand.
            $value = $relate ? $foreign->getId() : null;
            $this->rows[$type][$entity->getId()][$fk] = $value;
            $entity->f[$fk] = $value;
            $entity->fetched[$fk] = $value;
        }

        // ---- record routes ---------------------------------------------------------------------

        /** POST /<Entity>/<id>/<link>: record link hooks, then relate. */
        public function recordLink(string $type, string $id, string $link, string $foreignId, bool $hooksOnly = false): void
        {
            $entity = $this->load($type, $id);
            $foreign = $this->load(FakePlatform::LINK_DEFS[$type][$link][1] ?? $type, $foreignId);

            foreach ($this->recordHooks($type, 'BeforeLink') as $hook) {
                $hook->process($entity, $link, $foreign);
            }

            if (!$hooksOnly) {
                $this->relate($entity, $link, $foreign, ['api' => true]);
            }
        }

        public function recordUnlink(string $type, string $id, string $link, string $foreignId, bool $hooksOnly = false): void
        {
            $entity = $this->load($type, $id);
            $foreign = $this->load(FakePlatform::LINK_DEFS[$type][$link][1] ?? $type, $foreignId);

            foreach ($this->recordHooks($type, 'BeforeUnlink') as $hook) {
                $hook->process($entity, $link, $foreign);
            }

            if (!$hooksOnly) {
                $this->unrelate($entity, $link, $foreign, ['api' => true]);
            }
        }

        public function recordDelete(string $type, string $id, bool $hooksOnly = false): void
        {
            $entity = $this->load($type, $id);

            foreach ($this->recordHooks($type, 'BeforeDelete') as $hook) {
                $hook->process($entity, new \Espo\Core\Record\DeleteParams());
            }

            if (!$hooksOnly) {
                $this->remove($entity);
            }
        }

        /** The ORM remove: before-remove hooks, then the row goes. */
        public function remove(Entity $entity): void
        {
            $this->runHooks($entity->getEntityType(), 'beforeRemove', $entity, []);
            unset($this->rows[$entity->getEntityType()][$entity->getId()]);
        }

        public function recordCreateInput(Entity $entity): void
        {
            foreach ($this->recordHooks($entity->getEntityType(), 'BeforeCreateInput') as $hook) {
                $hook->process($entity, new \Espo\Core\Record\CreateParams());
            }
        }

        public function recordUpdateInput(Entity $entity): void
        {
            foreach ($this->recordHooks($entity->getEntityType(), 'BeforeUpdateInput') as $hook) {
                $hook->process($entity, new \Espo\Core\Record\UpdateParams());
            }
        }

        private function recordHooks(string $type, string $name): array
        {
            $file = $this->customDir . "/Resources/metadata/recordDefs/$type.json";
            $meta = is_file($file) ? json_decode((string) file_get_contents($file), true) : [];
            $key = match ($name) {
                'BeforeLink' => 'beforeLinkHookClassNameList',
                'BeforeUnlink' => 'beforeUnlinkHookClassNameList',
                'BeforeDelete' => 'beforeDeleteHookClassNameList',
                'BeforeCreateInput' => 'beforeCreateHookClassNameList',
                'BeforeUpdateInput' => 'beforeUpdateHookClassNameList',
            };
            $out = [];

            foreach ($meta[$key] ?? [] as $class) {
                $out[] = new $class($this->guard());
            }

            return $out;
        }

        // ---- queries issued by the custom code ---------------------------------------------------

        public function executeQuery(Query $query): void
        {
            if ($this->failExecutor) {
                throw new \RuntimeException('cannot execute');
            }

            $raw = $query->getRaw();

            if ($query instanceof Update) {
                $table = $query->getIn();

                if ($table === 'AccountContact') {
                    foreach ($this->junction as &$row) {
                        if ($this->matches($row, $raw['whereClause'] ?? [])) {
                            $row = array_merge($row, $query->getSet());
                        }
                    }

                    return;
                }

                foreach ($this->rows[$table] ?? [] as $id => $row) {
                    if ($this->matches($row, $raw['whereClause'] ?? [])) {
                        $this->rows[$table][$id] = array_merge($row, $query->getSet());
                    }
                }

                return;
            }

            if ($query instanceof Delete) {
                $table = $query->getFrom();

                if ($table === 'AccountContact') {
                    $this->junction = array_values(array_filter(
                        $this->junction,
                        fn($row) => !$this->matches($row, $raw['whereClause'] ?? [])
                    ));

                    return;
                }

                foreach ($this->rows[$table] ?? [] as $id => $row) {
                    if ($this->matches($row, $raw['whereClause'] ?? [])) {
                        unset($this->rows[$table][$id]);
                    }
                }

                return;
            }

            throw new \LogicException('unexpected query ' . get_class($query));
        }

        private function matches(array $row, array $where): bool
        {
            foreach ($where as $k => $v) {
                if ((string) ($row[$k] ?? '') !== (string) $v) {
                    return false;
                }
            }

            return true;
        }

        /** @return list<FakeEntity> */
        public function selectAll(Select $query): array
        {
            $type = $query->getFrom();
            $where = $query->getRaw()['whereClause'] ?? [];
            $items = [];

            foreach (array_keys($this->rows[$type] ?? []) as $id) {
                $ids = (array) ($where['id'] ?? [$id]);

                if (in_array($id, $ids, true)) {
                    $items[] = $this->load($type, (string) $id);
                }
            }

            return $items;
        }
    }

    /**
     * Modules/Crm/Hooks/Contact/Accounts, reduced: makes the first linked firm primary when
     * there is none (before save); relates a changed primary firm and unrelates a cleared one
     * (after save); gives a contact linked to a firm with no primary that firm as primary
     * (after relate).
     */
    class CrmContactHook
    {
        public function __construct(private FakePlatform $platform)
        {}

        public function run(string $name, Entity $entity, array $options, array $data): void
        {
            /** @var FakeEntity $entity */
            if ($name === 'beforeSave') {
                $ids = (array) $entity->get('accountsIds');

                if (
                    ($entity->isAttributeChanged('accountId') || $entity->isAttributeChanged('accountsIds')) &&
                    empty($entity->get('accountId')) && $ids
                ) {
                    $entity->set('accountId', (string) array_values($ids)[0]);
                }

                return;
            }

            if ($name === 'afterSave') {
                $fetched = $entity->getFetched('accountId');
                $account = $entity->get('accountId');

                if (empty($account) && !empty($fetched)) {
                    $this->platform->unrelate($entity, 'accounts', $this->platform->seedOnly('Account', (string) $fetched));

                    return;
                }

                if (!empty($account) && $entity->isAttributeChanged('accountId')
                    && !in_array($account, $this->platform->linkedFirms($entity->getId()), true)) {
                    $this->platform->relate($entity, 'accounts', $this->platform->seedOnly('Account', (string) $account));
                }

                return;
            }

            if ($name === 'afterRelate' && ($data['relationName'] ?? null) === 'accounts') {
                if (empty($entity->get('accountId')) && empty($this->platform->rows['Contact'][$entity->getId()]['accountId'])) {
                    $this->platform->relate($entity, 'account', $data['foreignEntity']);
                }
            }
        }
    }

    /**
     * Modules/Crm/Hooks/Account/Contacts, reduced: when a contact is unlinked from the firm that
     * is its primary firm, the primary firm is cleared (saved on the contact).
     */
    class CrmAccountHook
    {
        public function __construct(private FakePlatform $platform)
        {}

        public function run(string $name, Entity $entity, array $options, array $data): void
        {
            if ($name !== 'afterUnrelate' || ($data['relationName'] ?? null) !== 'contacts') {
                return;
            }

            $foreign = $data['foreignEntity'];

            if ($foreign->get('accountId') && $foreign->get('accountId') === $entity->getId()) {
                $contact = $this->platform->load('Contact', $foreign->getId());
                $contact->set('accountId', null);
                $this->platform->save($contact);
            }
        }
    }
}
