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
