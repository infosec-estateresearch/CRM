<?php

namespace Espo\Custom\Classes\Identity\RecordHooks;

use Espo\Core\Record\Hook\LinkHook;
use Espo\Custom\Classes\Identity\IdentityGuard;
use Espo\ORM\Entity;

/**
 * CRM-IDINT-001R: Record link hook (recordDefs beforeLinkHookClassNameList): runs before the platform relates two records through the link route. Refuses a successor set by linking.
 * All rules live in IdentityGuard. No administrator or service-account exemption.
 *
 * @implements LinkHook<Entity>
 */
class BeforeLink implements LinkHook
{
    public function __construct(private IdentityGuard $guard)
    {}

    public function process(Entity $entity, string $link, Entity $foreignEntity): void
    {
        $this->guard->refuseLinkChange($entity, $link, $foreignEntity, true);
    }
}
