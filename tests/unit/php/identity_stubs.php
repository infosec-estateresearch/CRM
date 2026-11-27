<?php
/**
 * CRM-IDINT-001R: the only stand-ins for platform symbols the identity unit tests use.
 *
 * Everything light is the real EspoCRM code (loaded from the pinned reference through its
 * own autoloader): the exceptions, the hook interfaces, GeneralInvoker, the option classes,
 * the query builders and Select. Only the heavy collaborators are replaced below, and only
 * by symbols that exist in the reference with the same signature. tests/unit/
 * test_platform_reference.py checks that (rule 3C.2): a symbol the platform lacks, a missing
 * method or a different parameter list or return type fails the unit suite.
 *
 * Interfaces and classes are declared with the methods the custom code calls and nothing
 * else; behaviour lives in identity_fake.php, in the CrmTest namespace.
 */

namespace CrmTest {
    /** Where the stand-ins find the fake platform (a test double, not a platform symbol). */
    class Link
    {
        /** @var object|null */
        public static $platform = null;
    }
}

namespace Espo\ORM {
    interface Entity
    {
        public function getId(): string;

        public function set($attribute, $value = null): static;

        public function get(string $attribute);

        public function has(string $attribute): bool;

        public function getEntityType(): string;

        public function isNew(): bool;

        public function isAttributeChanged(string $name): bool;

        public function getFetched(string $attribute);
    }

    class EntityManager
    {
        public function getNewEntity(string $entityType): Entity
        {
            throw new \LogicException('stand-in: overridden by the fake platform');
        }

        public function getEntityById(string $entityType, string $id): ?Entity
        {
            throw new \LogicException('stand-in: overridden by the fake platform');
        }

        public function saveEntity(Entity $entity, array $options = []): void
        {
            throw new \LogicException('stand-in: overridden by the fake platform');
        }

        public function getQueryExecutor(): Executor\QueryExecutor
        {
            throw new \LogicException('stand-in: overridden by the fake platform');
        }

        public function getRDBRepository(string $entityType): Repository\RDBRepository
        {
            throw new \LogicException('stand-in: overridden by the fake platform');
        }

        public function getTransactionManager(): TransactionManager
        {
            throw new \LogicException('stand-in: overridden by the fake platform');
        }
    }

    /** CRM-IDINT-001R2: the transaction manager (ORM/TransactionManager.php; nested starts are savepoints). */
    class TransactionManager
    {
        public function isStarted(): bool
        {
            throw new \LogicException('stand-in: overridden by the fake platform');
        }

        public function run(\Closure $function)
        {
            throw new \LogicException('stand-in: overridden by the fake platform');
        }

        public function start(): void
        {
            throw new \LogicException('stand-in: overridden by the fake platform');
        }

        public function commit(): void
        {
            throw new \LogicException('stand-in: overridden by the fake platform');
        }

        public function rollback(): void
        {
            throw new \LogicException('stand-in: overridden by the fake platform');
        }
    }
}

namespace Espo\Core\Repositories {
    /**
     * CRM-IDINT-001R2: the platform's repository base class. The product's repository extends it;
     * save() hands over to the fake platform, which runs the platform's save (transaction when the
     * entity definition asks for one, then the hooks). The properties are the platform's own
     * protected ones, set by the fake because the real constructor needs the whole platform.
     */
    class Database
    {
        protected \Espo\ORM\EntityManager $entityManager;
        protected \Espo\ORM\Repository\HookMediator $hookMediator;

        public function save(\Espo\ORM\Entity $entity, array $options = []): void
        {
            \CrmTest\Link::$platform->saveWithinPlatformTransaction($entity, $options);
        }
    }
}

namespace Espo\ORM\Repository {
    class RDBRepository
    {
        public function clone(\Espo\ORM\Query\Select $query): RDBSelectBuilder
        {
            throw new \LogicException('stand-in: overridden by the fake platform');
        }
    }

    class RDBSelectBuilder
    {
        public function find(): \Espo\ORM\EntityCollection|\Espo\ORM\SthCollection
        {
            throw new \LogicException('stand-in: overridden by the fake platform');
        }
    }
}

namespace Espo\ORM\Repository {
    /**
     * CRM-IDINT-001R2: the relation object (ORM/Repository/RDBRelation.php), not final. The product's
     * relation class extends it; each operation hands over to the fake platform, which changes the
     * relation (mapper) and runs the after hooks, as the platform does.
     */
    class RDBRelation
    {
        private \Espo\ORM\Entity $subject;
        private string $relationName;

        public function __construct(
            \Espo\ORM\EntityManager $entityManager,
            \Espo\ORM\Entity $entity,
            string $relationName,
            HookMediator $hookMediator
        ) {
            $this->subject = $entity;
            $this->relationName = $relationName;
        }

        public function relate(\Espo\ORM\Entity $entity, ?array $columnData = null, array $options = []): void
        {
            \CrmTest\Link::$platform->relateWithinPlatform($this->subject, $this->relationName, $entity, $options);
        }

        public function unrelate(\Espo\ORM\Entity $entity, array $options = []): void
        {
            \CrmTest\Link::$platform->unrelateWithinPlatform($this->subject, $this->relationName, $entity, $options);
        }

        public function massRelate(\Espo\ORM\Query\Select $query, array $options = []): void
        {
            \CrmTest\Link::$platform->massRelateWithinPlatform($this->subject, $this->relationName, $query, $options);
        }
    }
}

namespace Espo\Entities {
    class User
    {
        public function getId(): string
        {
            throw new \LogicException('stand-in: overridden by the fake platform');
        }

        public function getUserName(): ?string
        {
            throw new \LogicException('stand-in: overridden by the fake platform');
        }
    }
}

namespace Espo\Core\Utils {
    class Metadata
    {
        public function get($key = null, $default = null)
        {
            throw new \LogicException('stand-in: overridden by the fake platform');
        }
    }
}
